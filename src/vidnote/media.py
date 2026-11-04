"""音频下载、whisper 模型下载与本地转写。

这条路径是为「视频没有可用字幕」准备的：用 yt-dlp 取音频，用 faster-whisper 在
本机转写，不把音频上传到任何服务。

两个依赖都是可选的：没装的时候基础功能照常工作，只有走到转写这一步才会提示安装。
模型第一次使用时才下载到缓存目录，下载进度通过 ``on_progress`` 回调交给调用方。
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .bilibili import Cue, VideoMeta

ProgressFn = Callable[[float, float], None]
StatusFn = Callable[[str], None]


class MediaError(RuntimeError):
    """缺少依赖、下载失败或转写失败。"""


# faster-whisper 支持的名字 → Hugging Face 仓库；体积用于没有网络元数据时的估算。
WHISPER_MODELS = {
    "tiny": ("Systran/faster-whisper-tiny", 75),
    "base": ("Systran/faster-whisper-base", 145),
    "small": ("Systran/faster-whisper-small", 485),
    "medium": ("Systran/faster-whisper-medium", 1500),
    "large-v3": ("Systran/faster-whisper-large-v3", 3100),
}
_WHISPER_FILES = (
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
)


class _QuietLogger:
    """把 yt-dlp 的输出压到最低，避免污染 --stdout 的笔记内容。"""

    def debug(self, message: str) -> None:  # noqa: D102
        pass

    def warning(self, message: str) -> None:  # noqa: D102
        pass

    def error(self, message: str) -> None:  # noqa: D102
        pass


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True


def cache_dir() -> Path:
    """找一个可写的缓存目录。

    Windows 上优先 ``%LOCALAPPDATA%``，但有些机器（或受限账户）那里不可写，
    所以依次回退到 ``~/.cache`` 和系统临时目录——缓存写不进去不该让功能直接挂掉。
    """
    override = os.environ.get("VIDNOTE_CACHE")
    if override:
        return Path(override)

    if os.name == "nt":
        candidates = [
            Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
            / "vidnote",
            Path.home() / ".cache" / "vidnote",
        ]
    else:
        candidates = [
            Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "vidnote",
            Path(tempfile.gettempdir()) / "vidnote",
        ]
    candidates.append(Path(tempfile.gettempdir()) / "vidnote")

    for candidate in candidates:
        if _writable(candidate):
            return candidate
    return Path(tempfile.gettempdir()) / "vidnote"


def _cache_file(bvid: str, page: int, model: str) -> Path:
    return cache_dir() / f"{bvid}_p{page}_{model}.json"


def load_cached(bvid: str, page: int, model: str) -> tuple[str, list[Cue]] | None:
    path = _cache_file(bvid, page, model)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        cues = [Cue(start=c["s"], end=c["e"], text=c["t"]) for c in payload["cues"]]
        return str(payload.get("language", "unknown")), cues
    except (json.JSONDecodeError, KeyError, TypeError, OSError):
        return None


def save_cached(bvid: str, page: int, model: str, language: str, cues: list[Cue]) -> Path:
    path = _cache_file(bvid, page, model)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "bvid": bvid,
        "page": page,
        "model": model,
        "language": language,
        "cues": [{"s": c.start, "e": c.end, "t": c.text} for c in cues],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _whisper_dir(model_size: str) -> Path:
    return cache_dir() / "whisper" / model_size


def whisper_model_ready(model_size: str) -> bool:
    target = _whisper_dir(model_size)
    return (target / "model.bin").exists() and (target / "config.json").exists()


class _NullFile:
    """给 tqdm 一个黑洞输出，进度我们自己画。"""

    def write(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


class _DownloadCounter:
    """把 huggingface_hub 每个文件的进度汇总成一个总进度。"""

    def __init__(self, total_hint: float, callback: ProgressFn | None) -> None:
        self._callback = callback
        self._lock = threading.Lock()
        self._per_file: dict[str, float] = {}
        self.done = 0.0
        self.total = float(total_hint)

    def register(self, key: str, total: float) -> None:
        with self._lock:
            if key in self._per_file:
                return
            self._per_file[key] = 0.0
            if not self.total and total:
                self.total += total

    def advance(self, key: str, amount: float) -> None:
        with self._lock:
            self.done += amount
            self._per_file[key] = self._per_file.get(key, 0.0) + amount
            done, total = self.done, self.total
        if self._callback and total:
            self._callback(done, total)


def _repo_size_bytes(repo_id: str, fallback_mb: int) -> float:
    """从 Hugging Face 元数据里取要下载文件的总大小。"""
    try:
        from huggingface_hub import HfApi  # noqa: PLC0415

        info = HfApi().model_info(repo_id, files_metadata=True)
        total = sum(
            int(getattr(sibling, "size", 0) or 0)
            for sibling in info.siblings
            if _allowed(str(getattr(sibling, "rfilename", "")))
        )
        if total:
            return float(total)
    except Exception:  # noqa: BLE001 - 元数据拿不到不影响下载
        pass
    return float(fallback_mb) * 1024 * 1024


def _allowed(name: str) -> bool:
    return any(name.startswith(pattern.rstrip(".*")) for pattern in _WHISPER_FILES)


def ensure_whisper_model(
    model_size: str = "small",
    *,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> Path:
    """确保 whisper 模型已下载，返回模型目录。

    模型不走 faster-whisper 自带的下载（它的进度条直接写 stderr，界面拿不到），
    而是自己调 ``snapshot_download``，用自定义 tqdm 把字节数汇总出来。
    """
    if model_size not in WHISPER_MODELS:
        raise MediaError(
            f"未知的 whisper 模型：{model_size}（可选：{', '.join(WHISPER_MODELS)}）"
        )
    target = _whisper_dir(model_size)
    if whisper_model_ready(model_size):
        return target

    try:
        from huggingface_hub import snapshot_download  # noqa: PLC0415
        from tqdm import tqdm
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise MediaError(
            "缺少 faster-whisper / huggingface_hub，请先安装：pip install 'vidnote[whisper]'"
        ) from exc

    repo_id, size_mb = WHISPER_MODELS[model_size]
    if on_status:
        on_status(f"正在下载 whisper {model_size} 模型（约 {size_mb} MB）…")
    total = _repo_size_bytes(repo_id, size_mb)
    counter = _DownloadCounter(total, on_progress)

    class ProgressTqdm(tqdm):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._key = str(kwargs.get("desc") or id(self))
            kwargs["file"] = _NullFile()
            super().__init__(*args, **kwargs)
            counter.register(self._key, float(self.total or 0))

        def update(self, n: float = 1) -> None:
            super().update(n)
            counter.advance(self._key, float(n))

    target.mkdir(parents=True, exist_ok=True)
    try:
        snapshot_download(
            repo_id,
            local_dir=str(target),
            allow_patterns=list(_WHISPER_FILES),
            tqdm_class=ProgressTqdm,
        )
    except Exception as exc:  # noqa: BLE001
        raise MediaError(f"下载 whisper 模型失败：{exc}") from exc

    if not whisper_model_ready(model_size):
        raise MediaError(f"whisper 模型下载后不完整：{target}")
    if on_progress:
        on_progress(counter.total, counter.total)
    return target


def download_audio(
    url: str,
    workdir: Path,
    *,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> Path:
    """用 yt-dlp 下载最佳音频轨，返回本地文件路径。"""
    try:
        import yt_dlp  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise MediaError("缺少 yt-dlp，请先安装：pip install 'vidnote[whisper]'") from exc

    def hook(data: dict[str, Any]) -> None:
        if not on_progress:
            return
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            done = data.get("downloaded_bytes") or 0
            if total:
                on_progress(float(done), float(total))
        elif data.get("status") == "finished":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            if total:
                on_progress(float(total), float(total))

    if on_status:
        on_status("正在下载音频…")
    options: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _QuietLogger(),
        "progress_hooks": [hook],
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
    except Exception as exc:  # yt-dlp 的异常类型很杂
        raise MediaError(f"下载音频失败：{exc}") from exc

    path = Path(filename)
    if not path.exists():
        raise MediaError(f"下载完成但找不到文件：{path}")
    return path


def cues_from_segments(segments: Iterable[Any]) -> list[Cue]:
    """把 faster-whisper 的 segment 对象转成 Cue，过滤空文本。"""
    cues: list[Cue] = []
    for segment in segments:
        text = str(getattr(segment, "text", "")).strip()
        if not text:
            continue
        cues.append(
            Cue(
                start=float(getattr(segment, "start", 0.0)),
                end=float(getattr(segment, "end", 0.0)),
                text=text,
            )
        )
    return cues


def transcribe(
    audio: Path,
    *,
    model_size: str = "small",
    language: str | None = None,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    """在本地转写，返回 (检测到的语言, 字幕条目)。"""
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise MediaError(
            "缺少 faster-whisper，请先安装：pip install 'vidnote[whisper]'"
        ) from exc

    try:
        model_dir = ensure_whisper_model(
            model_size, on_progress=on_progress, on_status=on_status
        )
        if on_status:
            on_status("正在本地转写…")
        model = WhisperModel(str(model_dir), device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio), language=language, vad_filter=True)
        total = float(getattr(info, "duration", 0.0) or 0.0)
        collected: list[Cue] = []
        for segment in segments:
            text = str(getattr(segment, "text", "")).strip()
            if text:
                collected.append(
                    Cue(
                        start=float(getattr(segment, "start", 0.0)),
                        end=float(getattr(segment, "end", 0.0)),
                        text=text,
                    )
                )
            if on_progress and total:
                on_progress(float(getattr(segment, "end", 0.0)), total)
    except MediaError:
        raise
    except Exception as exc:
        raise MediaError(f"转写失败：{exc}") from exc

    if not collected:
        raise MediaError("转写结果为空，可能是纯音乐或音频异常。")
    return str(getattr(info, "language", "unknown") or "unknown"), collected


def transcribe_video(
    meta: VideoMeta,
    page: int,
    *,
    model_size: str = "small",
    use_cache: bool = True,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    """完整流程：缓存 → 下载音频 → 转写 → 写缓存。"""
    if use_cache and (cached := load_cached(meta.bvid, page, model_size)):
        if on_status:
            on_status("正在读取转写缓存…")
        return cached

    url = f"{meta.url}?p={page}" if len(meta.pages) > 1 else meta.url
    with tempfile.TemporaryDirectory(prefix="vidnote-") as tmp:
        audio = download_audio(
            url, Path(tmp), on_progress=on_progress, on_status=on_status
        )
        language, cues = transcribe(
            audio,
            model_size=model_size,
            on_progress=on_progress,
            on_status=on_status,
        )

    if use_cache:
        save_cached(meta.bvid, page, model_size, language, cues)
    return language, cues
