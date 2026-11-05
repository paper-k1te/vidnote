"""弹幕高能时刻的离线测试。"""

import httpx

from vidnote.highlights import danmaku_seconds, high_energy_times


def test_picks_spaced_peaks() -> None:
    seconds = [105.0] * 20 + [405.0] * 10 + [300.0] * 2
    times = high_energy_times(seconds, 600, count=2, min_gap=60)
    assert times == [105.0, 405.0]


def test_min_gap_skips_nearby_peak() -> None:
    seconds = [100.0] * 20 + [115.0] * 15 + [400.0] * 5
    times = high_energy_times(seconds, 600, count=2, min_gap=30)
    assert times == [105.0, 405.0]


def test_empty_input_returns_nothing() -> None:
    assert high_energy_times([], 100) == []
    assert high_energy_times([1.0, 2.0], 100, count=0) == []


def test_danmaku_seconds_parses_xml() -> None:
    xml = (
        '<d p="12.5,1,25,16777215,0,0,0,0">哈</d>'
        '<d p="99,1,25,16777215,0,0,0,0">好</d>'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert danmaku_seconds(1, client=client) == [12.5, 99.0]
