from datetime import date, datetime, timezone

from vidnote.bilibili import Cue, Page, VideoMeta
from vidnote.note import NoteOptions, build_note, filename, fmt_ts, slugify, ts_link

META = VideoMeta(
    bvid="BV1xx411c7mD",
    aid=170001,
    title="一个测试视频",
    owner="某UP",
    duration=3723,
    pubdate=datetime(2024, 5, 1, tzinfo=timezone.utc),
    desc="这是简介。",
    pages=[Page(index=1, cid=111, title="上半场", duration=3723)],
    tags=["测试"],
)

CUES = [
    Cue(start=0, end=2, text="大家好"),
    Cue(start=754, end=760, text="这里是重点"),
]


def test_fmt_ts() -> None:
    assert fmt_ts(0) == "00:00"
    assert fmt_ts(75) == "01:15"
    assert fmt_ts(3723) == "1:02:03"


def test_ts_link_points_at_second() -> None:
    assert ts_link("https://www.bilibili.com/video/BV1", 754) == (
        "[12:34](https://www.bilibili.com/video/BV1?t=754)"
    )


def test_slugify_strips_illegal_chars() -> None:
    assert slugify('a/b:c*d?"e"') == "a-b-c-d-e"
    assert slugify("   ") == "untitled"


def test_filename_contains_date_and_bvid() -> None:
    name = filename(META, when=date(2026, 11, 4))
    assert name == "2026-11-04_一个测试视频_BV1xx411c7mD.md"


def test_build_note_has_frontmatter_and_links() -> None:
    text = build_note(META, CUES, options=NoteOptions(fetched=date(2026, 11, 4)))
    assert text.startswith("---")
    assert "title: 一个测试视频" in text
    assert "bvid: BV1xx411c7mD" in text
    assert "subtitle: available" in text
    assert "[12:34](https://www.bilibili.com/video/BV1xx411c7mD?t=754)" in text
    assert "这里是重点" in text


def test_build_note_without_subtitles_says_so() -> None:
    text = build_note(META, None, options=NoteOptions(fetched=date(2026, 11, 4)))
    assert "subtitle: none" in text
    assert "没有可用字幕" in text


def test_build_note_can_skip_description() -> None:
    text = build_note(
        META, CUES, options=NoteOptions(fetched=date(2026, 11, 4), include_desc=False)
    )
    assert "这是简介。" not in text


def test_build_note_records_source() -> None:
    text = build_note(
        META, CUES, options=NoteOptions(fetched=date(2026, 11, 4), source="my-blog")
    )
    assert "source_project: my-blog" in text


def test_keyframes_are_placed_next_to_matching_cue() -> None:
    frames = [(0.0, "x_frames/01_00-00.jpg"), (754.0, "x_frames/02_12-34.jpg")]
    text = build_note(
        META,
        CUES,
        options=NoteOptions(fetched=date(2026, 11, 4)),
        frames=frames,
    )
    # 第一张帧跟在 00:00 那句后面，第二张跟在 12:34 后面。
    first = text.index("大家好")
    second = text.index("这里是重点")
    assert first < text.index("01_00-00.jpg") < second
    assert second < text.index("02_12-34.jpg")
    assert "## 关键帧" not in text


def test_keyframes_without_transcript_get_their_own_section() -> None:
    text = build_note(
        META,
        None,
        options=NoteOptions(fetched=date(2026, 11, 4)),
        frames=[(60.0, "x_frames/01_01-00.jpg")],
    )
    assert "## 关键帧" in text
    assert "01_01-00.jpg" in text


def test_multipart_note_lists_pages() -> None:
    meta = VideoMeta(
        bvid="BV1",
        aid=1,
        title="多P视频",
        owner="UP",
        duration=10,
        pubdate=datetime(2024, 1, 1, tzinfo=timezone.utc),
        desc="",
        pages=[
            Page(index=1, cid=1, title="第一集", duration=5),
            Page(index=2, cid=2, title="第二集", duration=5),
        ],
    )
    text = build_note(meta, None, options=NoteOptions(fetched=date(2026, 11, 4), page=2))
    assert "## 分P" in text
    assert "P2 第二集" in text
