"""音频下载与本地转写。

这条路径是为「视频没有可用字幕」准备的：用 yt-dlp 取音频，用 faster-whisper 在
本机转写，不把音频上传到任何服务。

两个依赖都是可选的：没装的时候基础功能照常工作，只有走到转写这一步才会提示安装。
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .bilibili import Cue, VideoMeta

ProgressFn = Callable[[float, float], None]


class MediaError(RuntimeError):
    """缺少依赖、下载失败或转写失败。"""


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


def download_audio(url: str, workdir: Path) -> Path:
    """用 yt-dlp 下载最佳音频轨，返回本地文件路径。"""
    try:
        import yt_dlp  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise MediaError("缺少 yt-dlp，请先安装：pip install 'vidnote[whisper]'") from exc

    options: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _QuietLogger(),
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
) -> tuple[str, list[Cue]]:
    """在本地转写，返回 (检测到的语言, 字幕条目)。"""
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise MediaError(
            "缺少 faster-whisper，请先安装：pip install 'vidnote[whisper]'"
        ) from exc

    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
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
) -> tuple[str, list[Cue]]:
    """完整流程：缓存 → 下载音频 → 转写 → 写缓存。"""
    if use_cache and (cached := load_cached(meta.bvid, page, model_size)):
        return cached

    url = f"{meta.url}?p={page}" if len(meta.pages) > 1 else meta.url
    with tempfile.TemporaryDirectory(prefix="vidnote-") as tmp:
        audio = download_audio(url, Path(tmp))
        language, cues = transcribe(
            audio, model_size=model_size, on_progress=on_progress
        )

    if use_cache:
        save_cached(meta.bvid, page, model_size, language, cues)
    return language, cues
