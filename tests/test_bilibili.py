from datetime import datetime, timedelta

import httpx
import pytest

from vidnote.bilibili import BilibiliClient, BiliError, VideoId, parse_video_id


def test_parse_full_url_with_page() -> None:
    video = parse_video_id("https://www.bilibili.com/video/BV1xx411c7mD/?p=3&spm=1")
    assert video.bvid == "BV1xx411c7mD"
    assert video.page == 3


def test_parse_bare_bv_and_av() -> None:
    assert parse_video_id("BV1xx411c7mD").bvid == "BV1xx411c7mD"
    assert parse_video_id("av170001").aid == 170001


def test_parse_short_link() -> None:
    assert parse_video_id("https://b23.tv/BV1xx411c7mD").bvid == "BV1xx411c7mD"


def test_parse_rejects_garbage() -> None:
    with pytest.raises(BiliError):
        parse_video_id("https://example.com/not-a-video")


VIEW = {
    "code": 0,
    "data": {
        "bvid": "BV1xx411c7mD",
        "aid": 170001,
        "title": "测试视频",
        "desc": "简介正文",
        "duration": 3723,
        "pubdate": 1714521600,
        "owner": {"name": "某UP"},
        "pages": [
            {"page": 1, "cid": 111, "part": "上半场", "duration": 1800},
            {"page": 2, "cid": 222, "part": "下半场", "duration": 1923},
        ],
        "tags": [{"tag_name": "测试"}],
    },
}


def test_view_maps_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=VIEW)

    with BilibiliClient(transport=httpx.MockTransport(handler)) as client:
        meta = client.view(VideoId(bvid="BV1xx411c7mD"))

    assert meta.title == "测试视频"
    assert meta.owner == "某UP"
    assert len(meta.pages) == 2
    assert meta.pages[1].title == "下半场"
    # B 站时间戳是北京时间，日期不能按 UTC 算。
    assert meta.pubdate.utcoffset() == timedelta(hours=8)
    assert meta.pubdate.date().isoformat() == "2024-05-01"


def test_view_raises_on_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": -404, "message": "啥都木有"})

    with BilibiliClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(BiliError) as excinfo:
            client.view(VideoId(bvid="BV1xx411c7mD"))
    assert "-404" in str(excinfo.value)


def test_subtitles_returns_cues() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/x/player/v2"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "subtitle": {
                            "subtitles": [
                                {"lan": "zh-CN", "subtitle_url": "//example.com/sub.json"}
                            ]
                        }
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "body": [
                    {"from": 1.5, "to": 3.0, "content": "第一句"},
                    {"from": 4, "to": 5, "content": "第二句"},
                ]
            },
        )

    with BilibiliClient(transport=httpx.MockTransport(handler)) as client:
        result = client.subtitles("BV1xx411c7mD", 111)

    assert result is not None
    lang, cues = result
    assert lang == "zh-CN"
    assert [c.text for c in cues] == ["第一句", "第二句"]
    assert cues[0].start == 1.5


def test_subtitles_returns_none_when_absent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": {"subtitle": {"subtitles": []}}})

    with BilibiliClient(transport=httpx.MockTransport(handler)) as client:
        assert client.subtitles("BV1xx411c7mD", 111) is None


def _meta():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=VIEW))
    with BilibiliClient(transport=transport) as client:
        return client.view(VideoId(bvid="BV1xx411c7mD"))


def test_pubdate_is_timezone_aware() -> None:
    meta = _meta()
    assert isinstance(meta.pubdate, datetime)
    assert meta.pubdate.tzinfo is not None


DETAIL = {
    "code": 0,
    "data": {
        "View": {
            "bvid": "BV1xx411c7mD",
            "aid": 170001,
            "title": "详情 &amp; 测试",
            "desc": "简介",
            "duration": 3723,
            "pubdate": 1714521600,
            "owner": {"mid": 42, "name": "某UP", "face": "//i0.hdslb.com/face.jpg"},
            "pages": [{"page": 1, "cid": 111, "part": "上半场", "duration": 3723}],
            "tname": "科技区",
            "videos": 1,
            "copyright": 1,
            "dynamic": "作者的动态",
            "pic": "//i0.hdslb.com/bfs/archive/cover.jpg",
            "dimension": {"width": 1920, "height": 1080},
            "staff": [
                {"mid": 42, "name": "某UP", "title": "UP主"},
                {"mid": 43, "name": "合作者", "title": "参演"},
            ],
            "subtitle": {
                "list": [
                    {
                        "lan": "zh-CN",
                        "lan_doc": "中文（中国）",
                        "is_lock": True,
                        "subtitle_url": "",
                    }
                ]
            },
            "ugc_season": {
                "id": 8971607,
                "title": "测试合集",
                "intro": "合集简介",
                "mid": 42,
                "sections": [
                    {
                        "title": "正片",
                        "episodes": [
                            {
                                "bvid": "BV1xx411c7mD",
                                "title": "第一集",
                                "page": 1,
                                "arc": {"duration": 120},
                            },
                            {
                                "bvid": "BV1yy411c7mD",
                                "title": "第二集",
                                "page": 1,
                                "arc": {"duration": 60},
                            },
                        ],
                    }
                ],
            },
            "stat": {
                "view": 123456,
                "danmaku": 789,
                "reply": 45,
                "favorite": 6789,
                "coin": 1234,
                "share": 56,
                "like": 9999,
            },
        },
        "Tags": [
            {"tag_name": "Python"},
            {"tag_name": "教程"},
        ],
        "Card": {"mid": 42},
    },
}


def test_view_uses_detail_endpoint_and_stats() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/x/web-interface/view/detail")
        return httpx.Response(200, json=DETAIL)

    with BilibiliClient(transport=httpx.MockTransport(handler)) as client:
        meta = client.view(VideoId(bvid="BV1xx411c7mD"))

    assert meta.title == "详情 & 测试"
    assert meta.tags == ["Python", "教程"]
    assert meta.stats.view == 123456
    assert meta.stats.like == 9999
    assert meta.owner_mid == 42
    assert meta.owner_url == "https://space.bilibili.com/42"
    assert meta.tname == "科技区"
    assert meta.owner_face == "https://i0.hdslb.com/face.jpg"
    assert meta.cover == "https://i0.hdslb.com/bfs/archive/cover.jpg"
    assert meta.dimension == "1920×1080"
    assert [(person.name, person.title) for person in meta.staff] == [
        ("某UP", "UP主"),
        ("合作者", "参演"),
    ]
    assert meta.season is not None
    assert meta.season.title == "测试合集"
    assert [episode.bvid for episode in meta.season.episodes] == [
        "BV1xx411c7mD",
        "BV1yy411c7mD",
    ]
    assert meta.subtitle_tracks[0].label == "中文（中国）"
    assert meta.subtitle_tracks[0].locked is True


def test_resolve_expands_short_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "b23.tv":
            return httpx.Response(
                302, headers={"Location": "https://www.bilibili.com/video/BV1xx411c7mD"}
            )
        return httpx.Response(200, text="")

    with BilibiliClient(transport=httpx.MockTransport(handler)) as client:
        video = client.resolve("https://b23.tv/abc123")
        naked = client.resolve("b23.tv/abc123")

    assert video.bvid == "BV1xx411c7mD"
    assert naked.bvid == "BV1xx411c7mD"
