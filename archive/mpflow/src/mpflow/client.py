"""Thin client for the WeChat Official Account API.

Only the endpoints needed to take a Markdown file all the way to a published
article are wrapped here. Everything is plain HTTP; no browser, no login
automation, no reverse-engineered endpoints.

Reference: https://developers.weixin.qq.com/doc/offiaccount/
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

API_BASE = "https://api.weixin.qq.com"


class WeChatError(RuntimeError):
    """An error returned by the WeChat API."""

    def __init__(self, errcode: int, errmsg: str, endpoint: str) -> None:
        self.errcode = errcode
        self.errmsg = errmsg
        self.endpoint = endpoint
        hint = ""
        if errcode == 40164:
            hint = (
                "\nHint: this machine's IP is not in the Official Account's IP "
                "allowlist (设置与开发 → 基本配置 → IP 白名单)."
            )
        elif errcode in (40001, 42001):
            hint = "\nHint: AppSecret is wrong, or the access_token expired. Re-run the command."
        elif errcode == 48001:
            hint = "\nHint: this account type does not have the 发布 (publish) capability."
        super().__init__(f"[{endpoint}] {errcode}: {errmsg}{hint}")


class WeChatClient:
    """Minimal, synchronous client with an in-process token cache."""

    def __init__(
        self,
        appid: str,
        secret: str,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._appid = appid
        self._secret = secret
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._http = httpx.Client(timeout=timeout, transport=transport)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> WeChatClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals ---------------------------------------------------------

    def _parse(self, response: httpx.Response, endpoint: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise WeChatError(-1, f"non-JSON response: {response.text[:200]}", endpoint) from exc
        errcode = payload.get("errcode", 0)
        if errcode:
            raise WeChatError(errcode, payload.get("errmsg", ""), endpoint)
        return payload

    # -- auth --------------------------------------------------------------

    def access_token(self, *, force_refresh: bool = False) -> str:
        if not force_refresh and self._token and time.time() < self._token_expires_at:
            return self._token
        response = self._http.get(
            f"{API_BASE}/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": self._appid,
                "secret": self._secret,
            },
        )
        payload = self._parse(response, "token")
        self._token = payload["access_token"]
        # Refresh a minute early to avoid races with long requests.
        self._token_expires_at = time.time() + int(payload.get("expires_in", 7200)) - 60
        return self._token

    # -- drafts ------------------------------------------------------------

    def add_draft(self, articles: list[dict[str, Any]]) -> str:
        """Create a draft and return its ``media_id``."""
        token = self.access_token()
        response = self._http.post(
            f"{API_BASE}/cgi-bin/draft/add",
            params={"access_token": token},
            content=json.dumps({"articles": articles}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        payload = self._parse(response, "draft/add")
        return payload["media_id"]

    def publish(self, media_id: str) -> str:
        """Submit a draft for publishing; returns the ``publish_id``."""
        token = self.access_token()
        response = self._http.post(
            f"{API_BASE}/cgi-bin/freepublish/submit",
            params={"access_token": token},
            content=json.dumps({"media_id": media_id}).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        payload = self._parse(response, "freepublish/submit")
        return payload.get("publish_id", "")

    # -- media -------------------------------------------------------------

    def upload_thumb(self, path: Path | str) -> str:
        """Upload a permanent image and return its ``media_id`` (for the cover)."""
        token = self.access_token()
        path = Path(path)
        with path.open("rb") as handle:
            response = self._http.post(
                f"{API_BASE}/cgi-bin/material/add_material",
                params={"access_token": token, "type": "image"},
                files={"media": (path.name, handle, "image/png")},
            )
        payload = self._parse(response, "material/add_material")
        return payload["media_id"]

    def upload_content_image(self, path: Path | str) -> str:
        """Upload an in-body image and return the hosted ``mmbiz`` URL."""
        token = self.access_token()
        path = Path(path)
        with path.open("rb") as handle:
            response = self._http.post(
                f"{API_BASE}/cgi-bin/media/uploadimg",
                params={"access_token": token},
                files={"media": (path.name, handle, "image/png")},
            )
        payload = self._parse(response, "media/uploadimg")
        return payload["url"]
