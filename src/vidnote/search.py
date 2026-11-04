"""B 站视频搜索。

用的是 ``/x/web-interface/search/all/v2``：这个接口目前允许匿名访问，返回按类型
分组的结果，取其中 ``result_type == "video"`` 的那组即可。

另外两条路都试过，都不可用：

- ``/x/web-interface/search/type``（旧接口）：直接返回非 JSON，被挡了；
- ``/x/web-interface/wbi/search/type``：需要 wbi 签名，而且匿名访问返回
  ``-101 账号未登录``。

所以这里不做签名，也不要求 cookie；如果哪天这个接口也开始要登录，会在
``search`` 里抛出带提示的 ``BiliError``，而不是静默返回空列表。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from .bilibili import API, HEADERS, BiliError

_TAG_RE = re.compile(r"<[^>]+>")


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

    def search(self, keyword: str, *, limit: int = 10, page: int = 1) -> list[SearchResult]:
        keyword = keyword.strip()
        if not keyword:
            raise BiliError("搜索关键词不能为空。")

        response = self._http.get(
            f"{API}/x/web-interface/search/all/v2",
            params={"keyword": keyword, "page": page},
        )
        response.raise_for_status()
        payload = response.json()

        code = payload.get("code", 0)
        if code == -352:
            raise BiliError("搜索被风控拦截（-352）。稍后重试，或降低请求频率。")
        if code == -101:
            raise BiliError("搜索接口现在要求登录（-101）。这个接口的匿名访问可能已被关闭。")
        if code:
            raise BiliError(f"搜索失败 code={code}: {payload.get('message', '未知错误')}")

        data = payload.get("data") or {}
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
