"""B 站公开接口的最小封装。

只读、只调用公开的 web 接口，不模拟登录、不绕风控。部分视频（尤其是需要登录
或充电的视频）拿不到字幕，这时要么用 `--whisper` 本地转写，要么这个视频就
没有字幕可用——不会伪造内容。

接口参考：https://github.com/SocialSisterYi/bilibili-API-collect
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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

# B 站的时间戳都是北京时间；用 UTC 会让凌晨发布的视频日期差一天。
BILIBILI_TZ = timezone(timedelta(hours=8))

_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_AV_RE = re.compile(r"(?<![0-9A-Za-z])av(\d+)", re.IGNORECASE)
_PAGE_RE = re.compile(r"[?&]p=(\d+)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s<>\"'，。、；：）】]+", re.IGNORECASE)
_SHORT_RE = re.compile(r"(b23\.tv|bili2233\.cn)/([0-9A-Za-z]+)", re.IGNORECASE)


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
class Stats:
    """播放数据。"""

    view: int = 0
    danmaku: int = 0
    reply: int = 0
    favorite: int = 0
    coin: int = 0
    share: int = 0
    like: int = 0


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
    stats: Stats = field(default_factory=Stats)
    owner_mid: int = 0
    owner_face: str = ""
    tname: str = ""
    videos: int = 1
    copyright: int = 0
    dynamic: str = ""
    season_id: int = 0

    @property
    def url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"

    @property
    def owner_url(self) -> str:
        return f"https://space.bilibili.com/{self.owner_mid}" if self.owner_mid else ""


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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any) -> str:
    return html.unescape(str(value or "")).strip()


def _https(url: str) -> str:
    return "https:" + url if url.startswith("//") else url


class BilibiliClient:
    def __init__(
        self,
        *,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            timeout=timeout, headers=HEADERS, transport=transport, follow_redirects=True
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BilibiliClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._http.get(f"{API}{path}", params=params)
        response.raise_for_status()
        payload = response.json()
        code = payload.get("code", 0)
        if code:
            raise BiliError(f"接口 {path} 返回 code={code}: {payload.get('message', '未知错误')}")
        return payload.get("data") or {}

    def resolve(self, value: str) -> VideoId:
        """解析用户输入；遇到 b23.tv 短链时跟一次重定向。

        ``parse_video_id`` 是纯字符串解析，短链里没有 BV 号，必须联网展开。
        """
        try:
            return parse_video_id(value)
        except BiliError:
            match = _URL_RE.search(value)
            if match:
                url = match.group(0)
            elif short := _SHORT_RE.search(value):
                url = f"https://{short.group(1)}/{short.group(2)}"
            else:
                raise

        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            response = self._http.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BiliError(f"短链接展开失败：{exc}") from exc

        final = str(response.url)
        try:
            return parse_video_id(final)
        except BiliError:
            pass

        # 有些短链落在动态页，BV 号只在 HTML 里。
        if match := _BV_RE.search(response.text):
            return VideoId(bvid=match.group(1))
        raise BiliError(f"短链接没有指向视频：{final}")

    def view(self, video: VideoId) -> VideoMeta:
        params: dict[str, Any] = {"bvid": video.bvid} if video.bvid else {"aid": video.aid}

        # detail 接口一次带回 View、Tags、Card；plain view 不带标签。
        try:
            detail = self._get("/x/web-interface/view/detail", params)
        except BiliError:
            detail = {}
        data = detail.get("View") if isinstance(detail, dict) else None
        if not data:
            data = self._get("/x/web-interface/view", params)
        if not isinstance(data, dict) or not data.get("bvid"):
            raise BiliError("接口没有返回视频信息。")

        raw_tags = []
        if isinstance(detail, dict):
            raw_tags = detail.get("Tags") or detail.get("tags") or []
        if not raw_tags:
            raw_tags = data.get("tags") or []
        if not raw_tags and data.get("bvid"):
            try:
                tags_data = self._get("/x/tag/archive/tags", {"bvid": data["bvid"]})
                if isinstance(tags_data, list):
                    raw_tags = tags_data
            except BiliError:
                pass

        pages = [
            Page(
                index=_int(item.get("page"), i + 1),
                cid=_int(item.get("cid")),
                title=_text(item.get("part")),
                duration=_int(item.get("duration")),
            )
            for i, item in enumerate(data.get("pages") or [])
        ]
        if not pages:
            pages = [
                Page(
                    index=1,
                    cid=_int(data.get("cid")),
                    title=_text(data.get("title")),
                    duration=_int(data.get("duration")),
                )
            ]

        owner = data.get("owner") or {}
        stat = data.get("stat") or {}
        return VideoMeta(
            bvid=_text(data.get("bvid")),
            aid=_int(data.get("aid")),
            title=_text(data.get("title")),
            owner=_text(owner.get("name")),
            duration=_int(data.get("duration")),
            pubdate=datetime.fromtimestamp(_int(data.get("pubdate")), tz=BILIBILI_TZ),
            desc=_text(data.get("desc")),
            pages=pages,
            tags=[
                _text(tag.get("tag_name"))
                for tag in raw_tags
                if isinstance(tag, dict) and _text(tag.get("tag_name"))
            ],
            stats=Stats(
                view=_int(stat.get("view")),
                danmaku=_int(stat.get("danmaku")),
                reply=_int(stat.get("reply")),
                favorite=_int(stat.get("favorite")),
                coin=_int(stat.get("coin")),
                share=_int(stat.get("share")),
                like=_int(stat.get("like")),
            ),
            owner_mid=_int(owner.get("mid")),
            owner_face=_https(_text(owner.get("face"))),
            tname=_text(data.get("tname")),
            videos=_int(data.get("videos"), 1),
            copyright=_int(data.get("copyright")),
            dynamic=_text(data.get("dynamic")),
            season_id=_int(data.get("season_id")),
        )

    def subtitles(
        self, bvid: str, cid: int, aid: int | None = None
    ) -> tuple[str, list[Cue]] | None:
        """返回 (语言代码, 字幕列表)。没有字幕时返回 None。"""
        params: dict[str, Any] = {"bvid": bvid, "cid": cid}
        if aid:
            params["aid"] = aid
        data = self._get("/x/player/v2", params)
        if not isinstance(data, dict):
            return None
        tracks = ((data.get("subtitle") or {}).get("subtitles")) or []
        # 没有地址的轨道（登录后才能取）直接跳过。
        tracks = [track for track in tracks if str(track.get("subtitle_url") or "").strip()]
        if not tracks:
            return None

        # 优先中文（含 AI 中文字幕），其次第一条。
        track = next(
            (
                item
                for item in tracks
                if str(item.get("lan", "")).lower().startswith(("zh", "ai-zh"))
            ),
            tracks[0],
        )
        url = _https(str(track.get("subtitle_url", "")))
        if not url:
            return None

        response = self._http.get(
            url, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
        )
        response.raise_for_status()
        body = response.json().get("body") or []
        cues = [
            Cue(
                start=float(item.get("from", 0)),
                end=float(item.get("to", 0)),
                text=_text(item.get("content")),
            )
            for item in body
            if _text(item.get("content"))
        ]
        return str(track.get("lan", "zh")), cues
