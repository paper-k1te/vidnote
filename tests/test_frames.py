from pathlib import Path

from vidnote.frames import KeyFrame, pick_frames


def test_pick_prefers_high_scores() -> None:
    scores = [(0.5, 10.0), (0.9, 40.0), (0.2, 70.0), (0.7, 100.0)]
    picked = pick_frames(scores, max_frames=2, min_gap=5.0, threshold=0.05)
    assert [moment for moment, _ in picked] == [40.0, 100.0]


def test_pick_respects_min_gap() -> None:
    scores = [(0.9, 10.0), (0.8, 12.0), (0.7, 30.0)]
    picked = pick_frames(scores, max_frames=5, min_gap=8.0, threshold=0.05)
    assert [moment for moment, _ in picked] == [10.0, 30.0]


def test_pick_drops_low_scores() -> None:
    scores = [(0.4, 1.0), (0.01, 2.0), (0.001, 3.0)]
    picked = pick_frames(scores, max_frames=5, min_gap=0.5, threshold=0.05)
    assert [moment for moment, _ in picked] == [1.0]


def test_pick_caps_at_max_frames_and_sorts_by_time() -> None:
    scores = [(0.5, float(t)) for t in (100, 10, 50, 30)]
    picked = pick_frames(scores, max_frames=2, min_gap=1.0, threshold=0.05)
    assert len(picked) == 2
    assert [moment for moment, _ in picked] == sorted(moment for moment, _ in picked)


def test_pick_handles_no_candidates() -> None:
    assert pick_frames([], max_frames=3) == []
    assert pick_frames([(0.001, 5.0)], threshold=0.05) == []


def test_keyframe_relative_to() -> None:
    base = Path("C:/notes")
    frame = KeyFrame(seconds=12.0, score=0.5, path=base / "note_frames" / "01_00-12.jpg")
    assert frame.relative_to(base) == "note_frames/01_00-12.jpg"


def test_keyframe_relative_to_falls_back_outside_base() -> None:
    frame = KeyFrame(seconds=1.0, score=0.1, path=Path("D:/other/x.jpg"))
    assert frame.relative_to(Path("C:/notes")).endswith("x.jpg")
