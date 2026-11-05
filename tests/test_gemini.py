"""Gemini 转写链路的离线测试：切段、时间戳、JSON 解析与请求重试。"""

import json
import wave
from pathlib import Path

import httpx
import pytest

import vidnote.gemini as gemini
from vidnote.bilibili import Cue


def test_timestamp_seconds_accepts_mmss_and_numbers() -> None:
    assert gemini._timestamp_seconds(75) == 75.0
    assert gemini._timestamp_seconds("01:15") == 75.0
    assert gemini._timestamp_seconds("1:02:03") == 3723.0


def test_extract_json_from_markdown_fence() -> None:
    payload = gemini._extract_json('```json\n{"segments": []}\n```')
    assert payload == {"segments": []}


def test_segments_are_offset_and_clamped() -> None:
    payload = {
        "segments": [
            {"start": 0, "end": 2.5, "text": "第一句"},
            {"start": 2.5, "end": 99, "text": "第二句"},
        ]
    }
    cues = gemini._segments_to_cues(payload, offset=60.0, duration=10.0)
    assert [cue.text for cue in cues] == ["第一句", "第二句"]
    assert cues[0].start == 60.0
    assert cues[0].end == 62.5
    assert cues[1].end == 70.0


def test_segments_accept_string_timestamps() -> None:
    payload = {"segments": [{"timestamp": "00:05", "content": "你好"}]}
    cues = gemini._segments_to_cues(payload, offset=10.0, duration=30.0)
    assert cues[0].start == 15.0
    assert cues[0].text == "你好"


def _wav(path: Path, seconds: float) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(gemini.SAMPLE_RATE)
        handle.writeframes(b"\0\0" * int(gemini.SAMPLE_RATE * seconds))


def test_write_wav_chunks_splits_by_duration(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gemini, "CHUNK_SECONDS", 1)
    monkeypatch.setattr(gemini, "_CHUNK_SAMPLES", gemini.SAMPLE_RATE)
    source = tmp_path / "input.wav"
    _wav(source, 3)
    chunks = gemini._write_wav_chunks(source, tmp_path)
    assert len(chunks) == 3
    assert all(duration == 1.0 for _, duration in chunks)


def test_transcribe_audio_offsets_chunks(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gemini, "CHUNK_SECONDS", 1)
    monkeypatch.setattr(gemini, "_CHUNK_SAMPLES", gemini.SAMPLE_RATE)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    source = tmp_path / "input.wav"
    _wav(source, 3)

    def fake_post(body, *, key, model, client=None):
        assert key == "test-key"
        assert body["contents"][0]["parts"][0]["text"] == gemini._PROMPT
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "segments": [
                                            {
                                                "start": 0,
                                                "end": 0.8,
                                                "text": "一段话",
                                            }
                                        ]
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(gemini, "_post_chunk", fake_post)
    language, cues = gemini.transcribe_audio(source)
    assert language == "zh"
    assert [round(cue.start, 1) for cue in cues] == [0.0, 1.0, 2.0]
    assert all(isinstance(cue, Cue) for cue in cues)


def test_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(gemini.GeminiError, match="API Key"):
        gemini.api_key(None)


def test_post_chunk_retries_after_rate_limit(monkeypatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"segments": []}'}]}}
                ]
            },
        )

    monkeypatch.setattr(gemini.time, "sleep", lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        data = gemini._post_chunk(
            {"contents": []}, key="k", model="gemini-3.8-flash", client=client
        )
    assert calls["count"] == 2
    assert data["candidates"][0]["content"]["parts"][0]["text"] == '{"segments": []}'


def test_safety_block_is_an_error() -> None:
    with pytest.raises(gemini.GeminiError, match="SAFETY"):
        gemini._text_from_response(
            {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]}
        )


def test_text_fallback_uses_whole_chunk(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    source = tmp_path / "input.wav"
    _wav(source, 1)

    def fake_post(body, *, key, model, client=None):
        return {
            "candidates": [
                {"content": {"parts": [{"text": "这是纯文本，不是 JSON"}]}}
            ]
        }

    monkeypatch.setattr(gemini, "_post_chunk", fake_post)
    _, cues = gemini.transcribe_audio(source)
    assert len(cues) == 1
    assert cues[0].start == 0
    assert cues[0].end == 1
    assert cues[0].text.startswith("这是纯文本")
