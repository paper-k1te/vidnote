"""LLM 精修的离线测试：接口约定、分段映射、失败回退。"""

import json
from datetime import datetime, timezone

import httpx
import pytest

import vidnote.llm as llm
from vidnote.bilibili import Cue, Page, VideoMeta

META = VideoMeta(
    bvid="BV1xx411c7mD",
    aid=1,
    title="测试视频",
    owner="某UP",
    duration=60,
    pubdate=datetime(2024, 5, 1, tzinfo=timezone.utc),
    desc="",
    pages=[Page(index=1, cid=1, title="正片", duration=60)],
    tags=["测试"],
)

CUES = [
    Cue(start=0, end=2, text="大家号"),
    Cue(start=2, end=5, text="今天我们聊一个话题"),
    Cue(start=5, end=8, text="这个很重要"),
]


def test_api_key_required(monkeypatch) -> None:
    monkeypatch.delenv("VIDNOTE_LLM_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(llm.LlmError, match="API Key"):
        llm.api_key(None)


def test_endpoint_adds_chat_completions() -> None:
    assert llm.endpoint("https://api.deepseek.com/v1") == (
        "https://api.deepseek.com/v1/chat/completions"
    )
    assert llm.endpoint("https://api.deepseek.com/v1/chat/completions") == (
        "https://api.deepseek.com/v1/chat/completions"
    )
    assert llm.endpoint("https://api.deepseek.com/v1/") == (
        "https://api.deepseek.com/v1/chat/completions"
    )


def test_refine_rewrites_text_and_maps_points(monkeypatch) -> None:
    monkeypatch.setenv("VIDNOTE_LLM_KEY", "test-key")
    requested: list[str] = []

    def fake_chat(messages, *, key, base_url=None, model=None, client=None, retry_delay=1.0):
        assert key == "test-key"
        if messages[0]["content"] == llm._SUMMARY_SYSTEM:
            return "这是一段摘要。"
        requested.append(messages[-1]["content"])
        return json.dumps(
            {
                "segments": [
                    {"i": 0, "text": "大家好。"},
                    {"i": 2, "text": "这一点很重要。"},
                ],
                "points": [
                    {"i": 1, "title": "核心话题", "detail": "今天聊的话题。"}
                ],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(llm, "chat", fake_chat)
    result = llm.refine_cues(CUES, META, api_key_value="test-key")

    assert [cue.text for cue in result.cues] == [
        "大家好。",
        "今天我们聊一个话题",
        "这一点很重要。",
    ]
    assert [cue.start for cue in result.cues] == [0, 2, 5]
    assert result.points[0].seconds == 2
    assert result.points[0].title == "核心话题"
    assert result.summary == "这是一段摘要。"
    assert result.model == "deepseek-chat"
    assert "1. (00:02) 今天我们聊一个话题" in requested[0]


def test_failed_chunk_keeps_original(monkeypatch) -> None:
    monkeypatch.setenv("VIDNOTE_LLM_KEY", "test-key")
    monkeypatch.setattr(llm, "_CHUNK_CUES", 1)
    calls = {"count": 0}

    def fake_chat(messages, *, key, base_url=None, model=None, client=None, retry_delay=1.0):
        calls["count"] += 1
        if calls["count"] == 1:
            raise llm.LlmError("boom")
        if messages[0]["content"] == llm._SUMMARY_SYSTEM:
            return "摘要"
        return json.dumps(
            {"segments": [{"i": 0, "text": "精修后的句子。"}], "points": []},
            ensure_ascii=False,
        )

    monkeypatch.setattr(llm, "chat", fake_chat)
    result = llm.refine_cues(CUES, META, api_key_value="test-key")

    assert result.cues[0].text == "大家号"
    assert result.cues[1].text == "精修后的句子。"
    assert result.errors and "第 1 段" in result.errors[0]


def test_chat_retries_after_rate_limit(monkeypatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "好了"}}]},
        )

    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        text = llm.chat(
            [{"role": "user", "content": "hi"}],
            key="k",
            base_url="https://example.com/v1",
            client=client,
        )

    assert calls["count"] == 2
    assert text == "好了"


def test_chat_reports_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("blocked", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(llm.LlmError, match="连不上 LLM"):
            llm.chat(
                [{"role": "user", "content": "hi"}],
                key="k",
                base_url="https://example.com/v1",
                client=client,
            )


def test_extract_json_from_fence() -> None:
    payload = llm._extract_json('```json\n{"segments": []}\n```')
    assert payload == {"segments": []}
