"""网页界面的后端逻辑与页面测试，不联网。"""

from pathlib import Path

from vid2note.gui import (
    fetch_video,
    index_html,
    job_state,
    open_url,
    parse_transcribe_options,
    read_frame,
    reveal,
    reveal_folder,
    whisper_deps_state,
)
from vid2note.media import hf_endpoint


def test_index_has_core_controls() -> None:
    html = index_html()
    for needle in (
        "生成笔记",
        "搜索视频",
        "预览",
        "/api/fetch",
        "/api/search",
        "解析方案",
        "下载渠道",
        "登录 B 站",
        "hf-mirror",
        "pick-folder",
        "/api/pick-folder",
        "打开文件夹",
        "/api/reveal-folder",
        "安装 whisper 依赖",
        "/api/deps",
        "作者",
        "data-search-type",
        "打开空间",
        "/api/open-url",
    ):
        assert needle in html


def test_login_and_download_are_separate_views() -> None:
    """登录与下载从抓取表单里独立出来，各自是一个左侧入口。"""
    html = index_html()
    assert 'data-view="login"' in html
    assert 'data-view="download"' in html
    assert 'id="view-login"' in html
    assert 'id="view-download"' in html

    fetch_start = html.index('id="view-fetch"')
    login_start = html.index('id="view-login"')
    download_start = html.index('id="view-download"')
    assert fetch_start < login_start < download_start

    fetch_section = html[fetch_start:login_start]
    assert 'id="cookie"' not in fetch_section
    assert 'id="channel"' not in fetch_section
    assert 'id="cookie"' in html[login_start:download_start]
    assert 'id="channel"' in html[download_start:]


def test_hf_endpoint_maps_channels() -> None:
    assert hf_endpoint("mirror") == "https://hf-mirror.com"
    assert hf_endpoint("official") == "https://huggingface.co"
    assert hf_endpoint("auto") is None


def test_whisper_deps_state_has_install_flags() -> None:
    state = whisper_deps_state()
    for key in ("running", "phase", "installed", "installable", "size_mb"):
        assert key in state


def test_index_is_standalone_html() -> None:
    html = index_html()
    assert html.lstrip().startswith("<!doctype html>")
    assert "<script>" in html
    assert "http://" not in html  # 不引用外部资源


def test_index_explains_static_file_mode() -> None:
    """直接双击 HTML 时没有本地服务，页面要给出明确提示。"""
    html = index_html()
    assert 'location.protocol === "file:"' in html
    assert "vid2note gui" in html


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


def test_open_url_rejects_non_bilibili_links() -> None:
    assert "error" in open_url("https://example.com/")
    assert "error" in open_url("http://space.bilibili.com/1")
    assert "error" in open_url("javascript:alert(1)")


def test_reveal_rejects_missing_file(tmp_path: Path) -> None:
    result = reveal(str(tmp_path / "missing.md"))
    assert "error" in result


def test_reveal_rejects_empty() -> None:
    assert "error" in reveal("")


def test_reveal_folder_rejects_empty() -> None:
    assert "error" in reveal_folder("")


def test_reveal_folder_rejects_missing_folder(tmp_path: Path) -> None:
    result = reveal_folder(str(tmp_path / "missing" / "note.md"))
    assert "error" in result


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
    assert read_frame(str(note), "<note_frames/01.jpg>") == found
    assert read_frame(str(note), "/note_frames/01.jpg") == found
    assert read_frame(str(note), "</note_frames/01.jpg>") == found


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


def test_parse_transcribe_options() -> None:
    assert parse_transcribe_options({"transcribe": "vosk"}) == (True, "vosk-cn")
    assert parse_transcribe_options({"transcribe": "vosk-cn"}) == (True, "vosk-cn")
    assert parse_transcribe_options({"transcribe": True, "model": "vosk"}) == (True, "vosk-cn")
    assert parse_transcribe_options({"transcribe": "whisper-tiny"}) == (True, "tiny")
    assert parse_transcribe_options({"transcribe": True, "model": "tiny"}) == (True, "tiny")
    assert parse_transcribe_options({"transcribe": "none"}) == (False, "")
    assert parse_transcribe_options({"transcribe": ""}) == (False, "")
    assert parse_transcribe_options({}) == (False, "")
    assert parse_transcribe_options({"transcribe": True}) == (True, "small")


def test_vidnote_backwards_compat() -> None:
    import vidnote
    assert vidnote.__version__ == "0.4.0"
    assert hasattr(vidnote, "BilibiliClient")
    assert hasattr(vidnote, "build_note")
