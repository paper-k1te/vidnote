"""图形界面：本地 HTTP 服务 + 系统的 Edge/Chrome「应用窗口」。

为什么不用 WebView 库：pywebview 在 Python 3.13 上装不上（依赖 proxy_tools 没有
wheel），而 Electron/Tauri 会把体积推到几十上百 MB。

``msedge --app=<url>`` 是 Windows 自带的「无地址栏应用窗口」模式：外观和独立桌面
应用一样，体积零增加，WebView2 内核本身就是系统组件。

进程生命周期：界面每 3 秒 ping 一次 ``/api/ping``，窗口关掉后心跳停止，服务在
超时后自动退出，不会留下一个后台进程。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__, whisper_deps
from .bilibili import BilibiliClient, BiliError
from .media import ProgressFn, StatusFn, hf_endpoint
from .note import NoteOptions, build_note, filename
from .search import BilibiliSearch
from .storyboard import storyboard_frames

IDLE_EXIT_SECONDS = 12.0

def index_html() -> str:
    """读取界面 HTML（打包后从 _MEIPASS 里的 vidnote/ui 读）。"""
    path = Path(__file__).with_name("ui") / "index.html"
    return path.read_text(encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = f"vidnote/{__version__}"
    last_ping = time.time()
    seen_ping = False

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(
        self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._get()
        except Exception as exc:  # noqa: BLE001 - 任何异常都要回一个 JSON
            _log(f"GET {self.path} 失败：{exc}")
            self._json(
                {"error": f"本地服务异常：{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR
            )

    def _get(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            page = index_html().replace("__VERSION__", __version__)
            self._send(HTTPStatus.OK, page.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            engines = transcribe_engines()
            self._json(
                {
                    "ok": True,
                    "version": __version__,
                    "transcribe": any(engines.values()),
                    "engines": engines,
                    "engine_errors": dict(_engine_errors),
                    "whisper_deps": {
                        **whisper_deps_state(),
                        "available": engines["whisper"],
                    },
                }
            )
            return
        if parsed.path == "/api/ping":
            Handler.last_ping = time.time()
            Handler.seen_ping = True
            self._json({"ok": True})
            return
        if parsed.path == "/api/search":
            query = parse_qs(parsed.query)
            keyword = (query.get("q") or [""])[0]
            limit = int((query.get("limit") or ["8"])[0])
            kind = (query.get("type") or ["video"])[0]
            if kind == "author":
                self._json(search_authors(keyword, limit))
            else:
                self._json(search_videos(keyword, limit))
            return
        if parsed.path == "/api/job":
            query = parse_qs(parsed.query)
            self._json(job_state((query.get("id") or [""])[0]))
            return
        if parsed.path == "/api/deps":
            self._json(whisper_deps_state())
            return
        if parsed.path == "/api/frame":
            query = parse_qs(parsed.query)
            found = read_frame(
                (query.get("note") or [""])[0], (query.get("src") or [""])[0]
            )
            if found is None:
                self._json({"error": "找不到图片"}, HTTPStatus.NOT_FOUND)
                return
            body, content_type = found
            self._send(HTTPStatus.OK, body, content_type)
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._post()
        except Exception as exc:  # noqa: BLE001 - 任何异常都要回一个 JSON
            _log(f"POST {self.path} 失败：{exc}")
            self._json(
                {"error": f"本地服务异常：{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR
            )

    def _post(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/fetch":
            Handler.last_ping = time.time()
            self._json({"job": start_fetch(self._body())})
            return
        if parsed.path == "/api/pick-folder":
            Handler.last_ping = time.time()
            self._json(pick_folder())
            return
        if parsed.path == "/api/deps/install":
            Handler.last_ping = time.time()
            self._json(start_deps_install())
            return
        if parsed.path == "/api/open-url":
            self._json(open_url(self._body().get("url", "")))
            return
        if parsed.path == "/api/reveal-folder":
            self._json(reveal_folder(self._body().get("path", "")))
            return
        if parsed.path == "/api/reveal":
            self._json(reveal(self._body().get("path", "")))
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)


@dataclass
class Job:
    """一次抓取任务。抓取在后台线程跑，界面轮询进度，不会被长请求卡住。"""

    status: str = "running"
    phase: str = "准备中…"
    done: float = 0.0
    total: float = 0.0
    result: dict[str, Any] | None = None
    error: str | None = None
    created: float = field(default_factory=time.time)


_JOBS: dict[str, Job] = {}
_JOBS_LOCK = threading.Lock()


def start_fetch(payload: dict[str, Any]) -> str:
    job_id = uuid.uuid4().hex
    job = Job()
    with _JOBS_LOCK:
        _JOBS[job_id] = job

    def on_status(text: str) -> None:
        job.phase = text

    def on_progress(done: float, total: float) -> None:
        job.done = done
        job.total = total

    def run() -> None:
        try:
            result = fetch_video(
                payload, on_status=on_status, on_progress=on_progress
            )
        except Exception as exc:  # noqa: BLE001 - 后台线程里兜底
            result = {"error": f"抓取失败：{exc}"}
        job.result = result
        if "error" in result:
            job.status = "error"
            job.error = str(result["error"])
            job.phase = "失败"
        else:
            job.status = "done"
            job.phase = "完成"

    threading.Thread(target=run, daemon=True).start()
    return job_id


def job_state(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        return {"error": "任务不存在或已结束"}
    return {
        "status": job.status,
        "phase": job.phase,
        "done": job.done,
        "total": job.total,
        "result": job.result,
        "error": job.error,
    }


def search_videos(keyword: str, limit: int = 8) -> dict[str, Any]:
    try:
        with BilibiliSearch() as client:
            results = client.search(keyword, limit=limit)
    except BiliError as exc:
        _log(f"搜索「{keyword}」失败：{exc}")
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        _log(f"搜索「{keyword}」请求失败：{exc}")
        return {"error": f"请求失败：{exc}"}
    return {
        "results": [
            {
                "bvid": item.bvid,
                "title": item.title,
                "author": item.author,
                "duration": item.duration,
                "play": item.play,
            }
            for item in results
        ]
    }


def search_authors(keyword: str, limit: int = 8) -> dict[str, Any]:
    try:
        with BilibiliSearch() as client:
            results = client.search_authors(keyword, limit=limit)
    except BiliError as exc:
        _log(f"搜索作者「{keyword}」失败：{exc}")
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        _log(f"搜索作者「{keyword}」请求失败：{exc}")
        return {"error": f"请求失败：{exc}"}
    return {
        "type": "author",
        "results": [
            {
                "mid": item.mid,
                "name": item.name,
                "avatar": item.avatar,
                "fans": item.fans,
                "videos": item.videos,
                "sign": item.sign,
                "verified": item.verified,
                "url": item.url,
            }
            for item in results
        ],
    }


_engine_errors: dict[str, str] = {}


def transcribe_engines() -> dict[str, bool]:
    """后端可用的转写引擎。"""
    engines = {"vosk": False, "whisper": False, "gemini": False}
    try:
        import av  # noqa: F401, PLC0415
        import vosk  # noqa: F401, PLC0415

        engines["vosk"] = True
        _engine_errors.pop("vosk", None)
    except Exception as exc:  # noqa: BLE001
        _engine_errors["vosk"] = f"{type(exc).__name__}: {exc}"
    try:
        import av  # noqa: F401, PLC0415
        import yt_dlp  # noqa: F401, PLC0415

        engines["gemini"] = True
        _engine_errors.pop("gemini", None)
    except Exception as exc:  # noqa: BLE001
        _engine_errors["gemini"] = f"{type(exc).__name__}: {exc}"
    engines["whisper"] = whisper_deps.available()
    return engines


def transcription_available() -> bool:
    """任意一个引擎可用即可。"""
    return any(transcribe_engines().values())


_deps_lock = threading.Lock()
_deps_state: dict[str, Any] = {
    "running": False,
    "phase": "",
    "done": 0.0,
    "total": 0.0,
    "last_error": None,
}


def whisper_deps_state() -> dict[str, Any]:
    """whisper 依赖的安装状态，供界面轮询。"""
    with _deps_lock:
        state = dict(_deps_state)
    state["installed"] = whisper_deps.installed()
    state["installable"] = whisper_deps.installable()
    state["size_mb"] = whisper_deps.DOWNLOAD_MB
    state["import_error"] = whisper_deps.import_error()
    return state


def start_deps_install() -> dict[str, Any]:
    """后台下载 whisper 依赖；重复点击直接返回当前状态。"""
    with _deps_lock:
        already = bool(_deps_state["running"])
        if not already:
            _deps_state.update(
                running=True, phase="准备下载…", done=0.0, total=0.0, last_error=None
            )
    if already:
        return whisper_deps_state()

    def on_status(message: str) -> None:
        with _deps_lock:
            _deps_state["phase"] = message

    def on_progress(done: float, total: float) -> None:
        with _deps_lock:
            _deps_state["done"] = done
            _deps_state["total"] = total

    def run() -> None:
        try:
            whisper_deps.install(on_progress=on_progress, on_status=on_status)
            with _deps_lock:
                _deps_state.update(
                    running=False,
                    phase="安装完成",
                    done=_deps_state["total"],
                )
        except Exception as exc:  # noqa: BLE001 - 后台线程，错误要带回界面
            with _deps_lock:
                _deps_state.update(running=False, phase="安装失败", last_error=str(exc))

    threading.Thread(target=run, name="whisper-deps", daemon=True).start()
    return whisper_deps_state()


def fetch_video(
    payload: dict[str, Any],
    *,
    on_status: StatusFn | None = None,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    target = str(payload.get("target", "")).strip()
    page = int(payload.get("page") or 1)
    frames = int(payload.get("frames") or 0)
    outdir = str(payload.get("outdir", "")).strip()
    transcribe = bool(payload.get("transcribe"))
    # 空字符串表示不转写；给了值就按这个模型转写。
    model = str(payload.get("model") or "").strip() or ("small" if transcribe else "")
    cookie = str(payload.get("cookie") or "").strip()
    channel = str(payload.get("channel") or "auto").strip()
    gemini_key = str(payload.get("gemini_key") or "").strip()
    gemini_model = str(payload.get("gemini_model") or "").strip() or "gemini-2.5-flash"
    gemini_used = False

    if on_status:
        on_status("正在获取视频信息…")
    try:
        with BilibiliClient(cookie=cookie or None) as client:
            video_id = client.resolve(target)
            meta = client.view(video_id)
            page = min(max(page, 1), len(meta.pages))
            if on_status:
                on_status("正在获取字幕…")
            subtitle = client.subtitles(
                meta.bvid, meta.pages[page - 1].cid, meta.aid
            )
    except BiliError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"请求失败：{exc}"}

    cues = subtitle[1] if subtitle else None
    lang = subtitle[0] if subtitle else "none"
    warning: str | None = None

    if cues is None and model:
        engines = transcribe_engines()
        if model == "gemini":
            if not engines["gemini"]:
                return {
                    "error": "这个版本没有音频下载/解码能力，Gemini 转写不可用；请用完整版。"
                }
            from .gemini import GeminiError
            from .gemini import transcribe_video as gemini_transcribe

            try:
                lang, cues = gemini_transcribe(
                    meta,
                    page,
                    api_key_value=gemini_key,
                    model=gemini_model,
                    on_progress=on_progress,
                    on_status=on_status,
                )
                gemini_used = True
            except GeminiError as exc:
                return {"error": f"Gemini 转写失败：{exc}"}
        elif model.startswith("vosk"):
            if not engines["vosk"]:
                return {
                    "error": "这个版本没有内置 Vosk 转写。请用完整版（vidnote-app-full），"
                    "或在命令行 pip install 'vidnote[vosk]' 后运行 vidnote fetch --vosk。"
                }
            from .asr import AsrError
            from .asr import transcribe_video as vosk_transcribe

            try:
                lang, cues = vosk_transcribe(
                    meta,
                    page,
                    model=model,
                    on_progress=on_progress,
                    on_status=on_status,
                )
            except AsrError as exc:
                return {"error": f"本地转写失败：{exc}"}
        else:
            if not engines["whisper"]:
                return {
                    "error": "这个版本没有内置 whisper。先点界面里的「安装 whisper 依赖」，"
                    "或在命令行 pip install 'vidnote[whisper]' 后运行 vidnote fetch --whisper。"
                }
            from .media import MediaError, transcribe_video

            try:
                lang, cues = transcribe_video(
                    meta,
                    page,
                    model_size=model,
                    on_progress=on_progress,
                    on_status=on_status,
                    endpoint=hf_endpoint(channel),
                )
            except MediaError as exc:
                return {"error": f"本地转写失败：{exc}"}

    directory = Path(outdir) if outdir else Path.cwd()
    destination = directory / filename(meta)

    keyframes: list[tuple[float, str]] = []
    if frames:
        if on_status:
            on_status("正在提取关键帧…")
        try:
            out = destination.parent / f"{destination.stem}_frames"
            shots = storyboard_frames(meta.bvid, page, out, count=frames)
            keyframes = [
                (shot.seconds, shot.relative_to(destination.parent)) for shot in shots
            ]
        except Exception as exc:  # noqa: BLE001 - 关键帧失败不阻塞笔记
            warning = f"跳过关键帧：{exc}"

    note = build_note(
        meta,
        cues,
        options=NoteOptions(
            page=page, transcription="gemini" if gemini_used else ""
        ),
        subtitle_lang=lang,
        frames=keyframes,
    )

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(note, encoding="utf-8")
    except OSError as exc:
        return {"error": f"写入文件失败：{exc}"}

    result: dict[str, Any] = {
        "note": note,
        "path": str(destination),
        "frames": len(keyframes),
    }
    if warning:
        result["warning"] = warning
    return result


_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def read_frame(note_path: str, src: str) -> tuple[bytes, str] | None:
    """给预览区提供笔记旁边的关键帧图片。

    只允许读笔记所在目录里的图片，避免把本地任意文件暴露给页面。
    """
    if not note_path or not src:
        return None
    note = Path(note_path)
    if not note.exists():
        return None
    base = note.parent.resolve()
    try:
        target = (base / src).resolve()
        target.relative_to(base)
    except (OSError, ValueError):
        return None
    content_type = _IMAGE_TYPES.get(target.suffix.lower())
    if not content_type or not target.is_file():
        return None
    try:
        return target.read_bytes(), content_type
    except OSError:
        return None


def pick_folder() -> dict[str, Any]:
    """弹出系统文件夹选择器，返回用户选中的绝对路径。"""
    if os.name != "nt":
        return {"error": "当前系统不支持选择文件夹，请手动填写路径。"}

    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

    class BrowseInfo(ctypes.Structure):
        _fields_ = [
            ("hwndOwner", wintypes.HWND),
            ("pidlRoot", ctypes.c_void_p),
            ("pszDisplayName", wintypes.LPWSTR),
            ("lpszTitle", wintypes.LPCWSTR),
            ("ulFlags", wintypes.UINT),
            ("lpfn", ctypes.c_void_p),
            ("lParam", wintypes.LPARAM),
            ("iImage", ctypes.c_int),
        ]

    try:
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        user32 = ctypes.windll.user32

        shell32.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BrowseInfo)]
        shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
        shell32.SHGetPathFromIDListW.argtypes = [
            ctypes.c_void_p,
            wintypes.LPWSTR,
        ]
        shell32.SHGetPathFromIDListW.restype = wintypes.BOOL
        user32.GetForegroundWindow.restype = wintypes.HWND
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]

        initialized = ole32.CoInitialize(None) == 0
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            info = BrowseInfo()
            info.hwndOwner = user32.GetForegroundWindow()
            info.pszDisplayName = buffer
            info.lpszTitle = "选择 vidnote 输出目录"
            # 只允许真实文件夹，带编辑框和“新建文件夹”按钮。
            info.ulFlags = 0x0001 | 0x0010 | 0x0040

            pidl = shell32.SHBrowseForFolderW(ctypes.byref(info))
            if not pidl:
                return {"cancelled": True}
            try:
                path_buffer = ctypes.create_unicode_buffer(32768)
                if not shell32.SHGetPathFromIDListW(pidl, path_buffer):
                    return {"cancelled": True}
                return {"path": path_buffer.value}
            finally:
                ole32.CoTaskMemFree(pidl)
        finally:
            if initialized:
                ole32.CoUninitialize()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"打开文件夹选择器失败：{exc}"}


def reveal_folder(path: str) -> dict[str, Any]:
    """打开笔记所在的文件夹；如果是文件，就在资源管理器里选中它。"""
    if not path:
        return {"error": "没有可打开的文件夹"}
    target = Path(path)
    folder = target if target.is_dir() else target.parent
    if not folder.exists():
        return {"error": f"文件夹不存在：{folder}"}
    try:
        if os.name == "nt":
            if target.is_file():
                subprocess.Popen(  # noqa: S603
                    ["explorer.exe", f"/select,{target}"]
                )
            else:
                os.startfile(folder)  # type: ignore[attr-defined]  # noqa: S606
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(folder)])  # noqa: S603
    except OSError as exc:
        return {"error": f"打开文件夹失败：{exc}"}
    return {"ok": True}


def reveal(path: str) -> dict[str, Any]:
    if not path:
        return {"error": "没有可打开的文件"}
    target = Path(path)
    if not target.exists():
        return {"error": f"文件不存在：{path}"}
    try:
        if os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606
        else:
            import sys

            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(target)])  # noqa: S603
    except OSError as exc:
        return {"error": f"打开失败：{exc}"}
    return {"ok": True}


def open_url(url: str) -> dict[str, Any]:
    """在默认浏览器里打开 B 站页面（作者空间等）。"""
    parsed = urlparse(str(url).strip())
    if parsed.scheme != "https" or parsed.netloc not in {
        "space.bilibili.com",
        "www.bilibili.com",
        "b23.tv",
    }:
        return {"error": "只允许打开 B 站链接"}
    try:
        opened = webbrowser.open(parsed.geturl())
    except Exception as exc:  # noqa: BLE001
        return {"error": f"打开链接失败：{exc}"}
    if not opened:
        return {"error": "没有找到可用的浏览器"}
    return {"ok": True}


def find_app_browser() -> str | None:
    """找一个能开 ``--app`` 窗口的 Chromium 系浏览器。"""
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def open_app_window(url: str) -> subprocess.Popen[bytes] | None:
    """用 Edge/Chrome 的 --app 模式打开一个独立窗口，返回进程句柄。

    任何一步失败都返回 None（调用方会退回普通浏览器），绝不抛异常——
    界面打不开不应该让服务端也跟着挂掉。
    """
    browser = find_app_browser()
    if not browser:
        return None

    args = [
        browser,
        f"--app={url}",
        "--window-size=1180,820",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
    ]
    # 不指定 --user-data-dir：用用户自己的配置目录。临时 profile 会触发 Edge 的
    # 首次运行/同步引导，窗口先显示一片空白甚至被弹窗盖住。

    try:
        return subprocess.Popen(args, close_fds=True)  # noqa: S603
    except OSError:
        return None


def _message_box(text: str, title: str = "vidnote") -> None:
    """没有控制台时（GUI 版 exe）用系统弹窗提示错误。"""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    except Exception:  # noqa: BLE001
        pass


def _watchdog(server: ThreadingHTTPServer, timeout: float = 20.0) -> None:
    """界面关掉后自动退出，避免留下后台进程。

    页面每 3 秒 ping 一次；窗口关了心跳就断。等第一次心跳之后才开始计时，
    否则浏览器还没加载完就被判死。
    """
    started = time.time()
    while True:
        time.sleep(2)
        now = time.time()
        if Handler.seen_ping:
            if now - Handler.last_ping > timeout:
                _log("心跳超时，界面可能已关闭，退出")
                server.shutdown()
                return
        elif now - started > 120:
            _log("120 秒内没有收到心跳，退出")
            server.shutdown()
            return


def _log(message: str) -> None:
    """界面版 exe 没有控制台，诊断信息写文件；终端里同时也打印。"""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    try:
        log_path = Path(tempfile.gettempdir()) / "vidnote-ui.log"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    try:
        if sys.stdout is not None:
            print(message)
    except Exception:  # noqa: BLE001 - 没有 stdout 时忽略
        pass


def serve(*, port: int = 0, open_browser: bool = True, app_window: bool = False) -> None:
    """启动服务并打开界面，直到窗口关闭或 Ctrl+C。

    生命周期跟着窗口进程走：不再用心跳猜——页面没加载完就退出，会变成
    「拒绝连接」。窗口进程结束，服务才结束。
    """
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        _log(f"绑定端口失败：{exc}")
        _message_box(f"端口被占用，无法启动界面：{exc}")
        raise

    actual = server.server_address[1]
    url = f"http://127.0.0.1:{actual}/"
    _log(f"启动 {__version__}，监听 {url}")

    window: subprocess.Popen[bytes] | None = None
    if open_browser:
        if app_window:
            try:
                window = open_app_window(url)
            except Exception as exc:  # noqa: BLE001 - 界面失败不能拖垮服务端
                _log(f"打开应用窗口失败：{exc}")
                window = None
        if window is None:
            _log("退回默认浏览器")
            webbrowser.open(url)
        else:
            _log(f"已请求打开应用窗口（pid={window.pid}）")
            # 注意：Edge 已经在运行时，新进程只会把请求转交给已有实例然后立即退出。
            # 所以不能用「进程退出」来判断窗口关闭，只能靠页面心跳。

    threading.Thread(target=_watchdog, args=(server,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("收到 Ctrl+C，退出")
    except Exception as exc:  # noqa: BLE001
        _log(f"服务异常：{exc}")
        raise
    finally:
        server.server_close()
        if window is not None and window.poll() is None:
            window.terminate()
