"""网页界面的后端逻辑与页面测试，不联网。"""

from pathlib import Path

from vidnote.gui import fetch_video, index_html, job_state, read_frame, reveal


def test_index_has_core_controls() -> None:
    html = index_html()
    for needle in ("生成笔记", "搜索视频", "预览", "/api/fetch", "/api/search"):
        assert needle in html


def test_index_is_standalone_html() -> None:
    html = index_html()
    assert html.lstrip().startswith("<!doctype html>")
    assert "<script>" in html
    assert "http://" not in html  # 不引用外部资源


def test_index_explains_static_file_mode() -> None:
    """直接双击 HTML 时没有本地服务，页面要给出明确提示。"""
    html = index_html()
    assert 'location.protocol === "file:"' in html
    assert "vidnote gui" in html


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


def test_read_frame_serves_image_next_to_note(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("x", encoding="utf-8")
    frame = tmp_path / "note_frames" / "01.jpg"
    frame.parent.mkdir()
    frame.write_bytes(b"\xff\xd8\xff")

    found = read_frame(str(note), "note_frames/01.jpg")
    assert found is not None
    body, content_type = found
    assert body == b"\xff\xd8\xff"
    assert content_type == "image/jpeg"


def test_read_frame_blocks_path_traversal(tmp_path: Path) -> None:
    note = tmp_path / "sub" / "note.md"
    note.parent.mkdir()
    note.write_text("x", encoding="utf-8")
    secret = tmp_path / "secret.jpg"
    secret.write_bytes(b"secret")

    assert read_frame(str(note), "../secret.jpg") is None
    assert read_frame(str(note), "../secret.txt") is None


def test_job_state_rejects_unknown_id() -> None:
    assert "error" in job_state("missing")
