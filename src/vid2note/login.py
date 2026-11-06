"""B 站官方扫码登录。

用 passport 的二维码接口拿登录态，省得用户自己去开发者工具里翻 SESSDATA：
``generate()`` 返回二维码 URL、qrcode_key 和一张 PNG（data URL），
``poll()`` 轮询扫码状态，成功后把 Set-Cookie / 回调 URL 里的凭据拼成
``SESSDATA=...; bili_jct=...`` 交给前端保存。
"""

from __future__ import annotations

import base64
import io
from urllib.parse import parse_qs, urlparse

import httpx

from .bilibili import API, HEADERS

PASSPORT = "https://passport.bilibili.com"
_COOKIE_KEYS = ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid")


class LoginError(RuntimeError):
    """生成二维码或轮询失败。"""


def _cookie_from(response: httpx.Response, cross_url: str | None) -> str:
    values: dict[str, str] = {}
    for name in _COOKIE_KEYS:
        value = response.cookies.get(name)
        if value:
            values[name] = value
    if cross_url:
        query = parse_qs(urlparse(cross_url).query)
        for name in _COOKIE_KEYS:
            if name not in values and query.get(name):
                values[name] = query[name][0]
    return "; ".join(f"{name}={values[name]}" for name in _COOKIE_KEYS if name in values)


def _png_data_url(url: str) -> str:
    try:
        import qrcode  # noqa: PLC0415
    except ImportError:  # pragma: no cover - 依赖缺失时前端可以只显示链接
        return ""
    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def generate() -> dict:
    """生成登录二维码。"""
    try:
        with httpx.Client(headers=HEADERS, timeout=20.0) as client:
            response = client.get(f"{PASSPORT}/x/passport-login/web/qrcode/generate")
            payload = response.json()
    except httpx.HTTPError as exc:
        raise LoginError(f"连不上 B 站登录接口：{exc}") from exc
    if payload.get("code"):
        raise LoginError(f"生成二维码失败：{payload.get('message') or payload.get('code')}")
    data = payload.get("data") or {}
    url = str(data.get("url") or "")
    key = str(data.get("qrcode_key") or "")
    if not url or not key:
        raise LoginError("B 站没有返回二维码地址。")
    return {"url": url, "key": key, "image": _png_data_url(url)}


def poll(key: str) -> dict:
    """轮询扫码状态；成功后返回 cookie。"""
    if not key:
        raise LoginError("缺少 qrcode_key。")
    try:
        with httpx.Client(headers=HEADERS, timeout=20.0) as client:
            response = client.get(
                f"{PASSPORT}/x/passport-login/web/qrcode/poll",
                params={"qrcode_key": key},
            )
            payload = response.json()
    except httpx.HTTPError as exc:
        raise LoginError(f"轮询登录状态失败：{exc}") from exc
    if payload.get("code"):
        raise LoginError(f"登录接口错误：{payload.get('message') or payload.get('code')}")

    data = payload.get("data") or {}
    code = int(data.get("code", -1))
    message = str(data.get("message") or "")
    if code == 86101:
        return {"status": "waiting", "message": "等待扫码"}
    if code == 86090:
        return {"status": "scanned", "message": "已扫码，请在手机上确认"}
    if code == 86038:
        return {"status": "expired", "message": "二维码已过期，请刷新"}
    if code != 0:
        return {"status": "error", "message": message or f"未知状态 {code}"}

    cookie = _cookie_from(response, str(data.get("url") or ""))
    if "SESSDATA=" not in cookie:
        return {"status": "error", "message": "登录成功但没有拿到 SESSDATA，请重试"}
    user = nav(cookie)
    return {"status": "ok", "message": "登录成功", "cookie": cookie, "user": user}


def nav(cookie: str) -> dict:
    """用登录态读一下昵称，失败也不影响登录结果。"""
    if not cookie.strip():
        return {}
    try:
        with httpx.Client(
            headers={**HEADERS, "Cookie": cookie},
            timeout=15.0,
        ) as client:
            payload = client.get(f"{API}/x/web-interface/nav").json()
    except (httpx.HTTPError, ValueError):
        return {}
    data = payload.get("data") or {}
    if not data.get("isLogin"):
        return {}
    return {
        "name": str(data.get("uname") or ""),
        "mid": data.get("mid"),
        "face": str(data.get("face") or ""),
    }
