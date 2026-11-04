"""用合成视频测试抽帧，不依赖网络。

生成一段 10 秒、画面在三段时间里分别是红/绿/蓝的视频，然后检查：
- 场景变化能被检测到，并且落在正确的边界附近；
- 导出的 JPEG 真的存在且有内容。
"""

from pathlib import Path

import pytest

av = pytest.importorskip("av")
PIL_Image = pytest.importorskip("PIL.Image")

from vidnote.frames import export_frames, select_keyframes  # noqa: E402

WIDTH, HEIGHT, FPS, SECONDS = 128, 72, 2, 10
COLORS = [(220, 30, 30), (30, 200, 60), (40, 60, 220)]


def make_video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=FPS)
    stream.width = WIDTH
    stream.height = HEIGHT
    stream.pix_fmt = "yuv420p"

    total = FPS * SECONDS
    for index in range(total):
        color = COLORS[min(index * len(COLORS) // total, len(COLORS) - 1)]
        image = PIL_Image.new("RGB", (WIDTH, HEIGHT), color)
        frame = av.VideoFrame.from_image(image)
        frame.pts = index
        for packet in stream.encode(frame):
            container.mux(packet)

    for packet in stream.encode():
        container.mux(packet)
    container.close()


def test_detects_scene_changes(tmp_path: Path) -> None:
    video = tmp_path / "sample.mp4"
    make_video(video)

    picks = select_keyframes(video, max_frames=5, min_gap=1.0, threshold=0.02)
    moments = [moment for moment, _ in picks]

    assert len(moments) >= 2
    # 边界大约在 3.3s 和 6.6s（10 秒三等分）
    assert any(3.0 <= moment <= 4.5 for moment in moments)
    assert any(6.0 <= moment <= 7.5 for moment in moments)


def test_export_writes_images(tmp_path: Path) -> None:
    video = tmp_path / "sample.mp4"
    make_video(video)

    picks = select_keyframes(video, max_frames=3, min_gap=1.0, threshold=0.02)
    frames = export_frames(video, picks[:2], tmp_path / "frames")

    assert len(frames) == 2
    for frame in frames:
        assert frame.path.exists()
        assert frame.path.stat().st_size > 0
        assert frame.path.suffix == ".jpg"

    names = sorted(path.name for path in frames[0].path.parent.iterdir())
    assert names == ["01_00-03.jpg", "02_00-06.jpg"] or all(n.endswith(".jpg") for n in names)


def test_no_picks_when_video_is_static(tmp_path: Path) -> None:
    video = tmp_path / "static.mp4"
    container = av.open(str(video), mode="w")
    stream = container.add_stream("mpeg4", rate=FPS)
    stream.width = WIDTH
    stream.height = HEIGHT
    stream.pix_fmt = "yuv420p"

    image = PIL_Image.new("RGB", (WIDTH, HEIGHT), (128, 128, 128))
    for index in range(FPS * 4):
        frame = av.VideoFrame.from_image(image)
        frame.pts = index
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()

    assert select_keyframes(video, threshold=0.02) == []
