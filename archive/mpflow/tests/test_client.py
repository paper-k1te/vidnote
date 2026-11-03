import json

import httpx
import pytest

from mpflow.client import WeChatClient, WeChatError


def make_client(handler) -> WeChatClient:
    return WeChatClient("appid", "secret", transport=httpx.MockTransport(handler))


def test_token_is_cached() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})

    with make_client(handler) as client:
        assert client.access_token() == "tok"
        assert client.access_token() == "tok"
    assert calls["n"] == 1


def test_error_is_raised_with_hint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errcode": 40164, "errmsg": "invalid ip"})

    with make_client(handler) as client:
        with pytest.raises(WeChatError) as excinfo:
            client.access_token()
    assert excinfo.value.errcode == 40164
    assert "IP" in str(excinfo.value)


def test_add_draft_sends_utf8_content() -> None:
    captured: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
        captured["body"] = request.content
        return httpx.Response(200, json={"media_id": "m1"})

    with make_client(handler) as client:
        assert client.add_draft([{"title": "中文", "content": "<p>正文</p>"}]) == "m1"

    payload = json.loads(captured["body"].decode("utf-8"))
    assert payload["articles"][0]["title"] == "中文"
