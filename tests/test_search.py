import httpx
import pytest

from vid2note.bilibili import BiliError
from vid2note.search import BilibiliSearch

RESPONSE = {
    "code": 0,
    "data": {
        "result": [
            {"result_type": "activity", "data": []},
            {
                "result_type": "video",
                "data": [
                    {
                        "bvid": "BV1xx411c7mD",
                        "title": '<em class="keyword">测试</em>视频',
                        "author": "某UP",
                        "duration": "12:34",
                        "play": 12345,
                        "pubdate": 1700000000,
                    },
                    {"bvid": "", "title": "没有 bvid 的条目"},
                ],
            },
        ]
    },
}


def make(handler) -> BilibiliSearch:
    return BilibiliSearch(transport=httpx.MockTransport(handler))


def test_search_picks_video_group_and_strips_tags() -> None:
    with make(lambda r: httpx.Response(200, json=RESPONSE)) as client:
        results = client.search("测试", limit=10)

    assert len(results) == 1
    assert results[0].bvid == "BV1xx411c7mD"
    assert results[0].title == "测试视频"
    assert results[0].play == 12345
    assert results[0].url == "https://www.bilibili.com/video/BV1xx411c7mD"


def test_search_respects_limit() -> None:
    payload = {
        "code": 0,
        "data": {
            "result": [
                {
                    "result_type": "video",
                    "data": [
                        {"bvid": f"BV{i}", "title": f"t{i}", "author": "u", "duration": "1:00"}
                        for i in range(20)
                    ],
                }
            ]
        },
    }
    with make(lambda r: httpx.Response(200, json=payload)) as client:
        assert len(client.search("x", limit=3)) == 3


def test_search_reports_risk_control() -> None:
    with make(lambda r: httpx.Response(200, json={"code": -352, "message": "风控"})) as client:
        with pytest.raises(BiliError) as excinfo:
            client.search("测试")
    assert "风控" in str(excinfo.value)


def test_search_reports_login_requirement() -> None:
    payload = {"code": -101, "message": "账号未登录"}
    with make(lambda r: httpx.Response(200, json=payload)) as client:
        with pytest.raises(BiliError) as excinfo:
            client.search("测试")
    assert "登录" in str(excinfo.value)


def test_search_rejects_empty_keyword() -> None:
    with make(lambda r: httpx.Response(200, json=RESPONSE)) as client:
        with pytest.raises(BiliError):
            client.search("   ")


AUTHOR_RESPONSE = {
    "code": 0,
    "data": {
        "result": [
            {
                "mid": 546195,
                "uname": "老番茄",
                "upic": "//i0.hdslb.com/bfs/face/abc.jpg",
                "usign": "<em>游戏</em>区 UP 主",
                "fans": 20868240,
                "videos": 682,
                "official_verify": {"type": 0, "desc": "bilibili 知名游戏UP主"},
            },
            {"mid": 0, "uname": "没有 mid 的条目"},
        ]
    },
}


def test_search_authors_parses_fields() -> None:
    with make(lambda r: httpx.Response(200, json=AUTHOR_RESPONSE)) as client:
        results = client.search_authors("老番茄", limit=10)

    assert len(results) == 1
    assert results[0].mid == 546195
    assert results[0].name == "老番茄"
    assert results[0].avatar == "https://i0.hdslb.com/bfs/face/abc.jpg"
    assert results[0].sign == "游戏区 UP 主"
    assert results[0].fans == 20868240
    assert results[0].videos == 682
    assert results[0].verified == "bilibili 知名游戏UP主"
    assert results[0].url == "https://space.bilibili.com/546195"


def test_search_authors_respects_limit() -> None:
    payload = {
        "code": 0,
        "data": {
            "result": [
                {"mid": i, "uname": f"u{i}", "upic": "", "fans": 0, "videos": 0}
                for i in range(1, 11)
            ]
        },
    }
    with make(lambda r: httpx.Response(200, json=payload)) as client:
        assert len(client.search_authors("x", limit=3)) == 3


def test_search_authors_rejects_empty_keyword() -> None:
    with make(lambda r: httpx.Response(200, json=AUTHOR_RESPONSE)) as client:
        with pytest.raises(BiliError):
            client.search_authors("   ")


ALL_V2_AUTHOR_RESPONSE = {
    "code": 0,
    "data": {
        "result": [
            {
                "result_type": "bili_user",
                "data": [
                    {
                        "mid": 546195,
                        "uname": "老番茄",
                        "upic": "//i0.hdslb.com/bfs/face/abc.jpg",
                        "usign": "游戏区 UP 主",
                        "fans": 20868240,
                        "videos": 682,
                    }
                ],
            },
            {"result_type": "video", "data": []},
        ]
    },
}


def test_search_authors_falls_back_to_all_v2_on_412(monkeypatch) -> None:
    calls = {"type": 0}

    def handler(request) -> httpx.Response:
        if "search/type" in str(request.url):
            calls["type"] += 1
            return httpx.Response(412, json={"code": -412})
        return httpx.Response(200, json=ALL_V2_AUTHOR_RESPONSE)

    monkeypatch.setattr("vidnote.search.time.sleep", lambda _seconds: None)
    with make(handler) as client:
        results = client.search_authors("老番茄", limit=10)

    assert calls["type"] == 3
    assert len(results) == 1
    assert results[0].mid == 546195


def test_search_retries_after_412(monkeypatch) -> None:
    calls = {"count": 0}

    def handler(request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(412, json={"code": -412})
        return httpx.Response(200, json=RESPONSE)

    monkeypatch.setattr("vidnote.search.time.sleep", lambda _seconds: None)
    with make(handler) as client:
        results = client.search("测试")

    assert calls["count"] == 2
    assert len(results) == 1


def test_search_handles_empty_result() -> None:
    payload = {"code": 0, "data": {"result": []}}
    with make(lambda r: httpx.Response(200, json=payload)) as client:
        assert client.search("没有结果") == []
