"""原生窗口相关的纯逻辑测试（不创建窗口，CI 也能跑）。"""

from pathlib import Path

import pytest

from vid2note import gui_native

pytest.importorskip("tkinter")


def test_build_note_file_rejects_bad_target() -> None:
    result = gui_native.build_note_file("不是视频")
    assert "error" in result


def test_build_note_file_rejects_empty_target() -> None:
    assert "error" in gui_native.build_note_file("")


def test_build_note_file_rejects_out_of_range_page(monkeypatch) -> None:
    """分P 越界时应该给出提示，而不是抛异常。"""

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def resolve(self, target):
            from vid2note.bilibili import VideoId

            return VideoId(bvid="BV1")

        def view(self, video_id):
            from datetime import datetime, timezone

            from vid2note.bilibili import Page, VideoMeta

            return VideoMeta(
                bvid="BV1",
                aid=1,
                title="t",
                owner="u",
                duration=10,
                pubdate=datetime(2024, 1, 1, tzinfo=timezone.utc),
                desc="",
                pages=[Page(index=1, cid=1, title="p1", duration=10)],
            )

        def subtitles(self, bvid, cid, aid=None):
            return None

    monkeypatch.setattr(gui_native, "BilibiliClient", lambda: FakeClient())
    result = gui_native.build_note_file("BV1xx411c7mD", page=3)
    assert "error" in result
    assert "分P" in result["error"]


def test_main_module_exposes_main() -> None:
    assert callable(gui_native.main)


def test_build_note_file_writes_preview(monkeypatch, tmp_path: Path) -> None:
    """正常路径：写文件并返回内容。"""

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def resolve(self, target):
            from vid2note.bilibili import VideoId

            return VideoId(bvid="BV1xx411c7mD")

        def view(self, video_id):
            from datetime import datetime, timezone

            from vid2note.bilibili import Page, VideoMeta

            return VideoMeta(
                bvid="BV1xx411c7mD",
                aid=1,
                title="测试",
                owner="u",
                duration=10,
                pubdate=datetime(2024, 1, 1, tzinfo=timezone.utc),
                desc="d",
                pages=[Page(index=1, cid=1, title="p1", duration=10)],
            )

        def subtitles(self, bvid, cid, aid=None):
            return "zh", []

    monkeypatch.setattr(gui_native, "BilibiliClient", lambda: FakeClient())
    result = gui_native.build_note_file("BV1xx411c7mD", outdir=str(tmp_path))
    assert "error" not in result
    assert Path(result["path"]).exists()
    assert "title: 测试" in result["note"]
