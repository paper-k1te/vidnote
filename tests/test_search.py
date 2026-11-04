import httpx
import pytest

from vidnote.bilibili import BiliError
from vidnote.search import BilibiliSearch

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


def test_search_handles_empty_result() -> None:
    payload = {"code": 0, "data": {"result": []}}
    with make(lambda r: httpx.Response(200, json=payload)) as client:
        assert client.search("没有结果") == []
