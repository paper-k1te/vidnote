"""扫码登录的 Cookie 解析测试（不发网络请求）。"""

from __future__ import annotations

import httpx

from vid2note.login import _cookie_from


def _response(headers: list[tuple[str, str]]) -> httpx.Response:
    return httpx.Response(
        200,
        headers=headers,
        request=httpx.Request("GET", "https://passport.bilibili.com/"),
    )


def test_cookie_from_set_cookie_headers() -> None:
    response = _response([
        ("set-cookie", "SESSDATA=abc%2C123; Path=/; Domain=.bilibili.com"),
        ("set-cookie", "bili_jct=token; Path=/"),
        ("set-cookie", "DedeUserID=42; Path=/"),
    ])
    cookie = _cookie_from(response, None)
    assert cookie == "SESSDATA=abc%2C123; bili_jct=token; DedeUserID=42"


def test_cookie_from_cross_domain_url() -> None:
    response = _response([])
    cross = (
        "https://passport.biligame.com/crossDomain?SESSDATA=x&bili_jct=y"
        "&DedeUserID=42&gourl=https%3A%2F%2Fwww.bilibili.com"
    )
    assert _cookie_from(response, cross) == "SESSDATA=x; bili_jct=y; DedeUserID=42"
