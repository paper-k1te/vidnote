import json
from types import SimpleNamespace

from vid2note.bilibili import Cue
from vid2note.media import (
    cache_dir,
    cues_from_segments,
    load_cached,
    save_cached,
)


def test_cues_from_segments_filters_empty() -> None:
    segments = [
        SimpleNamespace(start=0.0, end=1.5, text="  你好  "),
        SimpleNamespace(start=1.5, end=2.0, text="   "),
        SimpleNamespace(start=2.0, end=3.0, text="世界"),
    ]
    cues = cues_from_segments(segments)
    assert [c.text for c in cues] == ["你好", "世界"]
    assert cues[0].start == 0.0
    assert cues[1].end == 3.0


def test_cache_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIDNOTE_CACHE", str(tmp_path))
    assert cache_dir() == tmp_path

    cues = [Cue(start=0, end=1, text="第一句"), Cue(start=1, end=2, text="第二句")]
    save_cached("BV1", 1, "small", "zh", cues)

    loaded = load_cached("BV1", 1, "small")
    assert loaded is not None
    language, restored = loaded
    assert language == "zh"
    assert [(c.start, c.text) for c in restored] == [(0, "第一句"), (1, "第二句")]


def test_cache_miss_and_corrupt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIDNOTE_CACHE", str(tmp_path))
    assert load_cached("BV2", 1, "small") is None

    target = tmp_path / "BV3_p1_small.json"
    target.write_text("not json", encoding="utf-8")
    assert load_cached("BV3", 1, "small") is None


def test_cache_key_includes_page_and_model(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIDNOTE_CACHE", str(tmp_path))
    save_cached("BV4", 2, "tiny", "zh", [Cue(0, 1, "x")])
    assert load_cached("BV4", 1, "tiny") is None
    assert load_cached("BV4", 2, "small") is None
    assert load_cached("BV4", 2, "tiny") is not None

    payload = json.loads((tmp_path / "BV4_p2_tiny.json").read_text(encoding="utf-8"))
    assert payload["page"] == 2
    assert payload["model"] == "tiny"
