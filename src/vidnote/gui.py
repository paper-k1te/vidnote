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
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .bilibili import BilibiliClient, BiliError, parse_video_id
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
        parsed = urlparse(self.path)
        if parsed.path == "/":
            page = index_html().replace("__VERSION__", __version__)
            self._send(HTTPStatus.OK, page.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self._json(
                {
                    "ok": True,
                    "version": __version__,
                    "transcribe": transcription_available(),
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
            self._json(search_videos(keyword, limit))
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/fetch":
            Handler.last_ping = time.time()
            self._json(fetch_video(self._body()))
            return
        if parsed.path == "/api/reveal":
            self._json(reveal(self._body().get("path", "")))
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def search_videos(keyword: str, limit: int = 8) -> dict[str, Any]:
    try:
        with BilibiliSearch() as client:
            results = client.search(keyword, limit=limit)
    except BiliError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
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


def transcription_available() -> bool:
    """后端是否装好了本地转写的依赖（faster-whisper + yt-dlp）。"""
    try:
        import faster_whisper  # noqa: F401, PLC0415
        import yt_dlp  # noqa: F401, PLC0415
    except Exception:  # noqa: BLE001
        return False
    return True


def fetch_video(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(payload.get("target", "")).strip()
    page = int(payload.get("page") or 1)
    frames = int(payload.get("frames") or 0)
    outdir = str(payload.get("outdir", "")).strip()
    transcribe = bool(payload.get("transcribe"))
    # 空字符串表示不转写；给了值就按这个模型转写（tiny / base / small）。
    model = str(payload.get("model") or "").strip() or ("small" if transcribe else "")

    try:
        video_id = parse_video_id(target)
    except BiliError as exc:
        return {"error": str(exc)}

    try:
        with BilibiliClient() as client:
            meta = client.view(video_id)
            if page < 1 or page > len(meta.pages):
                return {"error": f"这个视频只有 {len(meta.pages)} 个分P。"}
            subtitle = client.subtitles(meta.bvid, meta.pages[page - 1].cid)
    except BiliError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"请求失败：{exc}"}

    cues = subtitle[1] if subtitle else None
    lang = subtitle[0] if subtitle else "none"

    if cues is None and model:
        if not transcription_available():
            return {
                "error": "这个版本没有内置转写。请用完整版，或在命令行运行 "
                "vidnote fetch --whisper（需 pip install 'vidnote[whisper]'）。"
            }
        from .media import MediaError, transcribe_video

        try:
            lang, cues = transcribe_video(meta, page, model_size=model)
        except MediaError as exc:
            return {"error": f"本地转写失败：{exc}"}

    directory = Path(outdir) if outdir else Path.cwd()
    destination = directory / filename(meta)

    keyframes: list[tuple[float, str]] = []
    if frames:
        try:
            out = destination.parent / f"{destination.stem}_frames"
            shots = storyboard_frames(meta.bvid, page, out, count=frames)
            keyframes = [
                (shot.seconds, shot.relative_to(destination.parent)) for shot in shots
            ]
        except Exception as exc:  # noqa: BLE001
            return {"error": f"取关键帧失败：{exc}"}

    note = build_note(
        meta,
        cues,
        options=NoteOptions(page=page),
        subtitle_lang=lang,
        frames=keyframes,
    )

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(note, encoding="utf-8")
    except OSError as exc:
        return {"error": f"写入文件失败：{exc}"}

    return {"note": note, "path": str(destination), "frames": len(keyframes)}


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
