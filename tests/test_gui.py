"""网页界面的后端逻辑与页面测试，不联网。"""

from pathlib import Path

from vidnote.gui import INDEX_HTML, fetch_video, reveal


def test_index_has_core_controls() -> None:
    for needle in ("生成笔记", "搜索", "预览", "/api/fetch", "/api/search"):
        assert needle in INDEX_HTML


def test_index_is_standalone_html() -> None:
    assert INDEX_HTML.lstrip().startswith("<!doctype html>")
    assert "<script>" in INDEX_HTML
    assert "http://" not in INDEX_HTML  # 不引用外部资源


def test_fetch_rejects_bad_target() -> None:
    result = fetch_video({"target": "不是视频"})
    assert "error" in result


def test_fetch_rejects_empty_target() -> None:
    assert "error" in fetch_video({})


def test_reveal_rejects_missing_file(tmp_path: Path) -> None:
    result = reveal(str(tmp_path / "missing.md"))
    assert "error" in result


def test_reveal_rejects_empty() -> None:
    assert "error" in reveal("")
