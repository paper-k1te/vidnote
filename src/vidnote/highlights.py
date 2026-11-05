"""用弹幕密度估算 B 站「高能进度条」，挑关键帧时刻。

B 站播放器里的高能进度条本质上是弹幕密度曲线：某几秒弹幕突然变多，说明那一段
是全场焦点。这里下载弹幕 XML，按 10 秒分桶、相邻桶平滑，取峰值且彼此间隔足够远
的时刻。拿不到弹幕时返回空列表，调用方退回均匀取帧。
"""

from __future__ import annotations

import re
from collections import Counter

import httpx

from .bilibili import API, HEADERS, BiliError, VideoMeta

_D_TIME = re.compile(r'<d p="(\d+(?:\.\d+)?),')
_BUCKET = 10.0
_MIN_GAP = 30.0


def danmaku_seconds(cid: int, *, client: httpx.Client | None = None) -> list[float]:
    """取某个分P 的弹幕时间点（秒）。"""
    owns_client = client is None
    http = client or httpx.Client(headers=HEADERS, timeout=30.0)
    try:
        response = http.get(f"{API}/x/v1/dm/list.so", params={"oid": cid})
        response.raise_for_status()
        text = response.text
    except httpx.HTTPError as exc:
        raise BiliError(f"取弹幕失败：{exc}") from exc
    finally:
        if owns_client:
            http.close()
    return [float(value) for value in _D_TIME.findall(text)]


def high_energy_times(
    seconds: list[float],
    duration: float,
    *,
    count: int = 6,
    bucket: float = _BUCKET,
    min_gap: float = _MIN_GAP,
) -> list[float]:
    """把弹幕按时间分桶，挑出密度最高且彼此分开的时刻。"""
    if not seconds or count <= 0 or bucket <= 0:
        return []
    limit = duration if duration > 0 else max(seconds)
    counts: Counter[int] = Counter(
        int(moment // bucket) for moment in seconds if 0 <= moment <= limit
    )
    if not counts:
        return []

    smoothed = {
        key: counts.get(key - 1, 0) + counts[key] + counts.get(key + 1, 0)
        for key in counts
    }
    ranked = sorted(smoothed.items(), key=lambda item: (-item[1], item[0]))
    picked: list[float] = []
    for key, _score in ranked:
        moment = (key + 0.5) * bucket
        if any(abs(moment - other) < min_gap for other in picked):
            continue
        picked.append(moment)
        if len(picked) >= count:
            break
    return sorted(picked)


def highlight_times(meta: VideoMeta, page: int, *, count: int = 6) -> list[float]:
    """某个分P 的高能时刻；没有弹幕时返回空列表。"""
    if not meta.pages or not 1 <= page <= len(meta.pages):
        return []
    current = meta.pages[page - 1]
    try:
        seconds = danmaku_seconds(current.cid)
    except BiliError:
        return []
    return high_energy_times(
        seconds, float(current.duration or meta.duration), count=count
    )
