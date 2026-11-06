"""云端转写的纯逻辑测试（不发网络请求）。"""

from __future__ import annotations

import pytest

from vid2note.bilibili import Cue
from vid2note.cloud_asr import (
    CloudAsrError,
    _model_for,
    _segments_to_cues,
    resolve_provider,
)


def test_model_defaults() -> None:
    assert _model_for("gemini", None) == "gemini-2.5-flash"
    assert _model_for("gemini", "models/gemini-2.5-pro") == "gemini-2.5-pro"
    assert _model_for("whisper", "cloud") == "whisper-1"
    assert _model_for("whisper", "whisper-1") == "whisper-1"


def test_provider_explicit() -> None:
    assert resolve_provider("gemini") == "gemini"
    assert resolve_provider("whisper-api") == "whisper"
    assert resolve_provider("openai") == "whisper"
    assert resolve_provider("auto", api_key="AIza-test") == "gemini"


def test_provider_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("VID2NOTE_ASR_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(CloudAsrError):
        resolve_provider("auto")


def test_segments_offset_and_clamp() -> None:
    cues = _segments_to_cues(
        {
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "第一句"},
                {"start": 2.5, "end": 99.0, "text": "第二句"},
                {"start": 3.0, "text": "没有结束时间"},
            ]
        },
        offset=240.0,
        duration=60.0,
    )
    assert [cue.text for cue in cues] == ["第一句", "第二句", "没有结束时间"]
    assert cues[0] == Cue(start=240.0, end=242.5, text="第一句")
    assert cues[1].end == 300.0
    assert cues[2].start == 243.0


def test_parse_transcribe_options_cloud() -> None:
    from vid2note.gui import parse_transcribe_options

    assert parse_transcribe_options({"model": "cloud"}) == (True, "cloud")
    assert parse_transcribe_options({"model": "gemini"}) == (True, "gemini")
    assert parse_transcribe_options({"transcribe": "whisper-api"}) == (True, "whisper-api")
    assert parse_transcribe_options({"transcribe": True, "model": "vosk-cn"}) == (True, "vosk-cn")
