"""whisper 依赖的按需安装。

完整版 exe 只带 Vosk 和音频解码所需的东西；faster-whisper 的推理引擎
（ctranslate2 / onnxruntime / tokenizers 等）体积很大，默认不打包，改成
第一次要用 whisper 时单独下载一个依赖包。

依赖包由 ``scripts/build_whisper_deps.ps1`` 生成，作为 GitHub Release
附件发布；安装目录是 ``<缓存>/whisper-deps``，启动时临时挂到 ``sys.path``，
不会污染用户环境。
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import threading
import zipfile
from pathlib import Path

import httpx

from . import __version__
from .media import ProgressFn, StatusFn, cache_dir

# 依赖包的格式版本；改了包内容就加一，旧目录会被重新安装。
DEPS_REVISION = 1
DOWNLOAD_MB = 66
_REQUIRED = (
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "tokenizers",
    "huggingface_hub",
)
_MARKER = ".vidnote-deps.json"

_DLL_HANDLES: list[object] = []
_ACTIVATE_LOCK = threading.Lock()
_IMPORT_ERROR: str | None = None


class DepsError(RuntimeError):
    """依赖包下载或安装失败。"""


def deps_dir() -> Path:
    return cache_dir() / "whisper-deps"


def _marker_payload() -> dict[str, object]:
    return {"revision": DEPS_REVISION, "vidnote": __version__}


def installed() -> bool:
    """依赖已经装好、且版本匹配。"""
    root = deps_dir()
    if not all((root / name).is_dir() for name in _REQUIRED):
        return False
    try:
        payload = json.loads((root / _MARKER).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return int(payload.get("revision", 0)) == DEPS_REVISION


def _add_dll_dirs(root: Path) -> None:
    """把依赖里的原生库目录加进 DLL 搜索路径。"""
    if os.name != "nt":
        return
    with _ACTIVATE_LOCK:
        if _DLL_HANDLES:
            return
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            for folder in (entry, *(child for child in entry.iterdir() if child.is_dir())):
                try:
                    _DLL_HANDLES.append(os.add_dll_directory(str(folder)))
                except OSError:
                    continue


def activate() -> bool:
    """把已安装的依赖挂到 ``sys.path``，返回是否找到依赖目录。"""
    if not installed():
        return False
    root = str(deps_dir())
    if root not in sys.path:
        sys.path.append(root)
        importlib.invalidate_caches()
    _add_dll_dirs(deps_dir())
    return True


def available() -> bool:
    """whisper 依赖能否正常导入。"""
    global _IMPORT_ERROR
    activate()
    try:
        import ctranslate2  # noqa: F401, PLC0415
        import faster_whisper  # noqa: F401, PLC0415
    except Exception as exc:  # noqa: BLE001 - 缺依赖、DLL 加载失败都算不可用
        _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        return False
    _IMPORT_ERROR = None
    return True


def import_error() -> str | None:
    """最近一次导入失败的原因，供界面显示。"""
    return _IMPORT_ERROR


def installable() -> bool:
    """当前这个 exe 是否支持在线安装依赖。

    轻量版连 av / yt-dlp 都没有，装完 whisper 依赖也跑不起来，所以不提供。
    源码运行时请直接用 pip 安装。
    """
    if not getattr(sys, "frozen", False):
        return False
    try:
        import av  # noqa: F401, PLC0415
        import yt_dlp  # noqa: F401, PLC0415
    except Exception:  # noqa: BLE001
        return False
    return True


def download_url() -> str:
    """依赖包地址；测试时可以用环境变量指向本地文件。"""
    override = os.environ.get("VIDNOTE_WHISPER_DEPS_URL", "").strip()
    if override:
        return override
    name = f"vidnote-whisper-deps-{__version__}.zip"
    return f"https://github.com/paper-k1te/vidnote/releases/download/v{__version__}/{name}"


def _copy_local(source: Path, dest: Path, on_progress: ProgressFn | None) -> None:
    total = float(source.stat().st_size)
    done = 0.0
    with source.open("rb") as reader, dest.open("wb") as writer:
        while chunk := reader.read(1024 * 256):
            writer.write(chunk)
            done += len(chunk)
            if on_progress and total:
                on_progress(done, total)


def _download(url: str, dest: Path, on_progress: ProgressFn | None) -> None:
    local = Path(url)
    if url.startswith("file://"):
        local = Path(url[7:])
    if local.is_file():
        _copy_local(local, dest, on_progress)
        return

    timeout = httpx.Timeout(60.0, read=300.0)
    try:
        with httpx.stream(
            "GET", url, timeout=timeout, follow_redirects=True
        ) as response:
            response.raise_for_status()
            total = float(response.headers.get("Content-Length") or 0)
            done = 0.0
            with dest.open("wb") as handle:
                for chunk in response.iter_bytes(1024 * 256):
                    handle.write(chunk)
                    done += len(chunk)
                    if on_progress and total:
                        on_progress(done, total)
    except Exception as exc:  # noqa: BLE001
        raise DepsError(f"下载 whisper 依赖失败：{exc}") from exc


def _safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    for name in archive.namelist():
        parts = Path(name).parts
        if Path(name).is_absolute() or ".." in parts:
            raise DepsError(f"依赖包里含有不安全路径：{name}")
    try:
        archive.extractall(target, filter="data")
    except TypeError:  # pragma: no cover - Python 3.10 / 3.11
        archive.extractall(target)


def install(
    *,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> dict[str, object]:
    """下载并安装 whisper 依赖，返回状态字典。"""
    if installed() and available():
        return {"ok": True, "already": True}

    root = deps_dir()
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = root.parent / "whisper-deps-staging"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True, exist_ok=True)
    archive = stage / "deps.zip"

    url = download_url()
    if on_status:
        on_status(f"正在下载 whisper 依赖（约 {DOWNLOAD_MB} MB）…")
    try:
        _download(url, archive, on_progress)
    except DepsError:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(stage, ignore_errors=True)
        raise DepsError(f"下载 whisper 依赖失败：{exc}") from exc

    if on_status:
        on_status("正在解压 whisper 依赖…")
    unpacked = stage / "unpacked"
    try:
        with zipfile.ZipFile(archive) as bundle:
            _safe_extract(bundle, unpacked)
    except DepsError:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(stage, ignore_errors=True)
        raise DepsError(f"解压 whisper 依赖失败：{exc}") from exc
    finally:
        archive.unlink(missing_ok=True)

    missing = [name for name in _REQUIRED if not (unpacked / name).is_dir()]
    if missing:
        shutil.rmtree(stage, ignore_errors=True)
        raise DepsError(f"依赖包不完整，缺少：{', '.join(missing)}")

    (unpacked / _MARKER).write_text(
        json.dumps(_marker_payload(), ensure_ascii=False), encoding="utf-8"
    )
    if root.exists():
        try:
            shutil.rmtree(root)
        except OSError as exc:
            raise DepsError(
                f"旧的 whisper 依赖正在使用，先关掉应用再重装：{exc}"
            ) from exc
    unpacked.rename(root)
    shutil.rmtree(stage, ignore_errors=True)
    activate()
    if on_status:
        on_status("whisper 依赖安装完成")
    return {"ok": True, "path": str(root)}
