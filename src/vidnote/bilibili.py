"""B 站公开接口的最小封装。

只读、只调用公开的 web 接口，不模拟登录、不绕风控。部分视频（尤其是需要登录
或充电的视频）拿不到字幕，这时要么用 `--whisper` 本地转写，要么这个视频就
没有字幕可用——不会伪造内容。

接口参考：https://github.com/SocialSisterYi/bilibili-API-collect
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

API = "https://api.bilibili.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json",
}

_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_AV_RE = re.compile(r"av(\d+)", re.IGNORECASE)
_PAGE_RE = re.compile(r"[?&]p=(\d+)")


class BiliError(RuntimeError):
    """接口返回了非零 code，或者输入无法解析。"""


@dataclass(frozen=True)
class VideoId:
    bvid: str | None = None
    aid: int | None = None
    page: int = 1

    @property
    def key(self) -> str:
        return self.bvid or f"av{self.aid}"


@dataclass(frozen=True)
class Page:
    index: int
    cid: int
    title: str
    duration: int


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class VideoMeta:
    bvid: str
    aid: int
    title: str
    owner: str
    duration: int
    pubdate: datetime
    desc: str
    pages: list[Page] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"


def parse_video_id(value: str) -> VideoId:
    """从 URL、BV 号或 av 号里解析出视频标识。"""
    value = value.strip()
    if not value:
        raise BiliError("请输入 B 站视频链接、BV 号或 av 号。")

    page = 1
    if match := _PAGE_RE.search(value):
        page = max(1, int(match.group(1)))

    if match := _BV_RE.search(value):
        return VideoId(bvid=match.group(1), page=page)
    if match := _AV_RE.search(value):
        return VideoId(aid=int(match.group(1)), page=page)
    raise BiliError(f"无法识别的视频标识：{value}")


class BilibiliClient:
    def __init__(
        self,
        *,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(timeout=timeout, headers=HEADERS, transport=transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BilibiliClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._http.get(f"{API}{path}", params=params)
        response.raise_for_status()
        payload = response.json()
        code = payload.get("code", 0)
        if code:
            raise BiliError(f"接口 {path} 返回 code={code}: {payload.get('message', '未知错误')}")
        return payload.get("data") or {}

    def view(self, video: VideoId) -> VideoMeta:
        params: dict[str, Any] = {"bvid": video.bvid} if video.bvid else {"aid": video.aid}
        data = self._get("/x/web-interface/view", params)

        pages = [
            Page(
                index=int(item.get("page", i + 1)),
                cid=int(item["cid"]),
                title=str(item.get("part", "")),
                duration=int(item.get("duration", 0)),
            )
            for i, item in enumerate(data.get("pages") or [])
        ]
        if not pages:
            pages = [
                Page(
                    index=1,
                    cid=int(data["cid"]),
                    title=str(data.get("title", "")),
                    duration=int(data.get("duration", 0)),
                )
            ]

        return VideoMeta(
            bvid=str(data["bvid"]),
            aid=int(data["aid"]),
            title=str(data.get("title", "")),
            owner=str((data.get("owner") or {}).get("name", "")),
            duration=int(data.get("duration", 0)),
            pubdate=datetime.fromtimestamp(int(data.get("pubdate", 0)), tz=timezone.utc),
            desc=str(data.get("desc", "")),
            pages=pages,
            tags=[
                str(tag.get("tag_name", ""))
                for tag in (data.get("tags") or [])
                if tag.get("tag_name")
            ],
        )

    def subtitles(self, bvid: str, cid: int) -> tuple[str, list[Cue]] | None:
        """返回 (语言代码, 字幕列表)。没有字幕时返回 None。"""
        data = self._get("/x/player/v2", {"bvid": bvid, "cid": cid})
        tracks = ((data.get("subtitle") or {}).get("subtitles")) or []
        if not tracks:
            return None

        # 优先中文，其次第一条。
        track = next((t for t in tracks if str(t.get("lan", "")).startswith("zh")), tracks[0])
        url = str(track.get("subtitle_url", ""))
        if url.startswith("//"):
            url = "https:" + url
        if not url:
            return None

        response = self._http.get(url, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
        response.raise_for_status()
        body = response.json().get("body") or []
        cues = [
            Cue(
                start=float(item.get("from", 0)),
                end=float(item.get("to", 0)),
                text=str(item.get("content", "")).strip(),
            )
            for item in body
            if str(item.get("content", "")).strip()
        ]
        return str(track.get("lan", "zh")), cues
