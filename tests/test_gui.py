"""网页界面的后端逻辑与页面测试，不联网。"""

from pathlib import Path

from vidnote.gui import fetch_video, index_html, reveal


def test_index_has_core_controls() -> None:
    html = index_html()
    for needle in ("生成笔记", "搜索视频", "预览", "/api/fetch", "/api/search"):
        assert needle in html


def test_index_is_standalone_html() -> None:
    html = index_html()
    assert html.lstrip().startswith("<!doctype html>")
    assert "<script>" in html
    assert "http://" not in html  # 不引用外部资源


def test_index_uses_design_tokens() -> None:
    """界面沿用 cc-switch 的设计 token：浅底灰阶 + 单一强调色。"""
    html = index_html()
    assert "--bg-sidebar: #f5f5f7" in html
    assert "--action-bg: #f97316" in html


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
