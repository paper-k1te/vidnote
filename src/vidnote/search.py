"""B 站视频与作者搜索。

视频走 ``/x/web-interface/search/all/v2``：这个接口目前允许匿名访问，返回按类型
分组的结果，取其中 ``result_type == "video"`` 的那组即可。

作者走 ``/x/web-interface/search/type`` + ``search_type=bili_user``，实测匿名可用。
两条路都不做签名、不要求 cookie；如果哪天接口开始要登录，会抛出带提示的
``BiliError``，而不是静默返回空列表。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .bilibili import API, HEADERS, BiliError

_TAG_RE = re.compile(r"<[^>]+>")


class SearchBlocked(BiliError):
    """B 站返回 412 风控页；作者搜索会退回 all/v2 接口。"""


@dataclass(frozen=True)
class SearchResult:
    bvid: str
    title: str
    author: str
    duration: str
    play: int
    pubdate: int

    @property
    def url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"


@dataclass(frozen=True)
class AuthorResult:
    mid: int
    name: str
    avatar: str
    fans: int
    videos: int
    sign: str
    verified: str

    @property
    def url(self) -> str:
        return f"https://space.bilibili.com/{self.mid}"


def _https(url: str) -> str:
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://"):
        return f"https://{url[7:]}"
    return url


class BilibiliSearch:
    def __init__(
        self, *, timeout: float = 15.0, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._http = httpx.Client(timeout=timeout, headers=HEADERS, transport=transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BilibiliSearch:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _data(
        self, path: str, params: dict[str, Any], *, retries: int = 1
    ) -> dict[str, Any]:
        attempts = retries + 1
        response = None
        for attempt in range(attempts):
            response = self._http.get(f"{API}{path}", params=params)
            if response.status_code != 412:
                break
            if attempt + 1 < attempts:
                # B 站偶发的风控页，隔一秒再试。
                time.sleep(1.0)
        if response is None:  # pragma: no cover - attempts 至少为 1
            raise BiliError("搜索请求没有发出。")
        if response.status_code == 412:
            raise SearchBlocked("搜索触发了 B 站风控（HTTP 412）。")
        response.raise_for_status()
        payload = response.json()

        code = payload.get("code", 0)
        if code == -352:
            raise BiliError("搜索被风控拦截（-352）。稍后重试，或降低请求频率。")
        if code == -101:
            raise BiliError("搜索接口现在要求登录（-101）。这个接口的匿名访问可能已被关闭。")
        if code:
            raise BiliError(f"搜索失败 code={code}: {payload.get('message', '未知错误')}")
        return payload.get("data") or {}

    def search(self, keyword: str, *, limit: int = 10, page: int = 1) -> list[SearchResult]:
        keyword = keyword.strip()
        if not keyword:
            raise BiliError("搜索关键词不能为空。")

        data = self._data(
            "/x/web-interface/search/all/v2",
            {"keyword": keyword, "page": page},
        )
        items: list[dict[str, Any]] = []
        for group in data.get("result") or []:
            if group.get("result_type") == "video":
                items = list(group.get("data") or [])
                break

        results: list[SearchResult] = []
        for item in items[:limit]:
            bvid = str(item.get("bvid", ""))
            if not bvid:
                continue
            results.append(
                SearchResult(
                    bvid=bvid,
                    title=_TAG_RE.sub("", str(item.get("title", ""))).strip(),
                    author=str(item.get("author", "")),
                    duration=str(item.get("duration", "")),
                    play=int(item.get("play", 0) or 0),
                    pubdate=int(item.get("pubdate", 0) or 0),
                )
            )
        return results

    def search_authors(
        self, keyword: str, *, limit: int = 10, page: int = 1
    ) -> list[AuthorResult]:
        keyword = keyword.strip()
        if not keyword:
            raise BiliError("搜索关键词不能为空。")

        try:
            data = self._data(
                "/x/web-interface/search/type",
                {"search_type": "bili_user", "keyword": keyword, "page": page},
                retries=2,
            )
            items = list((data.get("result") or [])[:limit])
        except SearchBlocked:
            # 专用作者接口偶发 412；all/v2 更稳定，至少给出最匹配的作者。
            data = self._data(
                "/x/web-interface/search/all/v2",
                {"keyword": keyword, "page": page},
            )
            items = []
            for group in data.get("result") or []:
                if group.get("result_type") == "bili_user":
                    items = list(group.get("data") or [])
                    break

        results: list[AuthorResult] = []
        for item in items:
            mid = int(item.get("mid") or 0)
            if not mid:
                continue
            verify = item.get("official_verify") or {}
            results.append(
                AuthorResult(
                    mid=mid,
                    name=_TAG_RE.sub("", str(item.get("uname", ""))).strip(),
                    avatar=_https(str(item.get("upic", ""))),
                    fans=int(item.get("fans", 0) or 0),
                    videos=int(item.get("videos", 0) or 0),
                    sign=_TAG_RE.sub("", str(item.get("usign", ""))).strip(),
                    verified=str(verify.get("desc") or "").strip(),
                )
            )
        return results
