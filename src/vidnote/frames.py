"""关键帧提取。

思路：把视频按固定频率采样成小尺寸灰度图，比较相邻帧的差异；差异大的地方就是
「画面变了」——PPT 翻页、代码切换、镜头切换都落在这里。然后取分数最高的若干帧，
按时间排序，导出成 JPEG。

完全不依赖 AI，也不需要系统装 ffmpeg：下载用 yt-dlp，解码用 PyAV，存图用 Pillow。
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bilibili import VideoMeta

# 采样时的缩略尺寸：够用来判断「画面变没变」，又不至于太慢。
_THUMB = (64, 36)


class FrameError(RuntimeError):
    """下载、解码或导出失败。"""


@dataclass(frozen=True)
class KeyFrame:
    seconds: float
    score: float
    path: Path

    def relative_to(self, base: Path) -> str:
        try:
            return self.path.relative_to(base).as_posix()
        except ValueError:
            return self.path.as_posix()


class _QuietLogger:
    def debug(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...


def download_video(url: str, workdir: Path) -> Path:
    """下载一个低分辨率版本，只为了抽帧，不追求画质。"""
    try:
        import yt_dlp  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise FrameError("缺少 yt-dlp，请先安装：pip install 'vidnote[frames]'") from exc

    options: dict[str, Any] = {
        # B 站的画面和声音是分开的 DASH 流；抽帧只需要画面，选一个低分辨率视频流，
        # 这样既不用合并（也就不需要系统 ffmpeg），下载量也小。
        "format": "worstvideo[height<=480][ext=mp4]/worstvideo[ext=mp4]/worstvideo",
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
    except Exception as exc:
        raise FrameError(
            f"下载视频失败：{exc}\n"
            "如果一直超时，多半是视频 CDN 在当前网络不可达。"
            "可以自己把视频下载到本地，再用 --video 指定文件。"
        ) from exc

    path = Path(filename)
    if not path.exists():
        raise FrameError(f"下载完成但找不到文件：{path}")
    return path


def pick_frames(
    scores: list[tuple[float, float]],
    *,
    max_frames: int = 8,
    min_gap: float = 8.0,
    threshold: float = 0.05,
) -> list[tuple[float, float]]:
    """从 [(分数, 时间)] 里挑出既显著又彼此分开的关键帧，按时间升序返回。"""
    ranked = sorted(scores, key=lambda item: item[0], reverse=True)
    picked: list[tuple[float, float]] = []
    for score, moment in ranked:
        if score < threshold:
            break
        if all(abs(moment - other) >= min_gap for other, _ in picked):
            picked.append((moment, score))
        if len(picked) >= max_frames:
            break
    picked.sort(key=lambda item: item[0])
    return picked


def select_keyframes(
    video: Path,
    *,
    max_frames: int = 8,
    min_gap: float = 0.0,
    sample_fps: float = 2.0,
    threshold: float = 0.05,
) -> list[tuple[float, float]]:
    """返回 [(时间秒, 变化分数)]，按时间升序。

    ``min_gap`` 为 0 时按视频长度自动计算：短视频也能选出多个关键帧。
    """
    try:
        import av  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise FrameError("缺少 av 或 Pillow，请先安装：pip install 'vidnote[frames]'") from exc

    container = av.open(str(video))
    try:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"

        previous: bytes | None = None
        last_sample = -1.0
        scores: list[tuple[float, float]] = []

        for frame in container.decode(stream):
            if frame.time is None:
                continue
            moment = float(frame.time)
            if moment - last_sample < 1.0 / sample_fps:
                continue
            last_sample = moment

            image = frame.to_image().convert("L").resize(_THUMB, Image.Resampling.BILINEAR)
            current = image.tobytes()
            if previous is not None and len(current) == len(previous):
                total = sum(abs(a - b) for a, b in zip(current, previous, strict=False))
                scores.append((total / (len(current) * 255.0), moment))
            previous = current
    finally:
        container.close()

    duration = scores[-1][1] if scores else 0.0
    if min_gap <= 0:
        # 让关键帧在时间上尽量分散：总长 / 目标帧数的一半，至少 2 秒。
        min_gap = max(2.0, duration / max(max_frames, 1) / 2)

    return pick_frames(
        scores, max_frames=max_frames, min_gap=min_gap, threshold=threshold
    )


def export_frames(video: Path, picks: list[tuple[float, float]], outdir: Path) -> list[KeyFrame]:
    """按时间点定位并导出 JPEG。"""
    import av  # noqa: PLC0415

    outdir.mkdir(parents=True, exist_ok=True)
    results: list[KeyFrame] = []

    container = av.open(str(video))
    try:
        stream = container.streams.video[0]
        for index, (moment, score) in enumerate(picks, start=1):
            container.seek(int(moment * 1_000_000), stream=stream, backward=True)
            frame = next(container.decode(stream), None)
            if frame is None:
                continue
            name = f"{index:02d}_{int(moment // 60):02d}-{int(moment % 60):02d}.jpg"
            path = outdir / name
            frame.to_image().save(path, quality=82, optimize=True)
            results.append(KeyFrame(seconds=moment, score=score, path=path))
    finally:
        container.close()

    return results


def extract_keyframes(
    meta: VideoMeta,
    page: int,
    outdir: Path,
    *,
    max_frames: int = 8,
    video_path: Path | None = None,
) -> list[KeyFrame]:
    """下载 → 选帧 → 导出，一步到位。

    传入 ``video_path`` 时跳过下载，直接分析本地文件（网络拿不到视频流时很有用）。
    """
    if video_path is not None:
        picks = select_keyframes(video_path, max_frames=max_frames)
        return export_frames(video_path, picks, outdir) if picks else []

    url = f"{meta.url}?p={page}" if len(meta.pages) > 1 else meta.url
    with tempfile.TemporaryDirectory(prefix="vidnote-frames-") as tmp:
        video = download_video(url, Path(tmp))
        picks = select_keyframes(video, max_frames=max_frames)
        if not picks:
            return []
        return export_frames(video, picks, outdir)
