"""用 B 站现成的雪碧图取缩略帧。

``/x/player/videoshot`` 这个接口返回的是一张「拼图」：一张 JPEG 里按网格排好了
若干个时间点的画面，附一份时间点列表。所以取帧不需要下载视频，也不需要解码，
只要下载一张几百 KB 的图片，再按格子裁开。

这是 ``--frames`` 的默认实现：快、省流量、不依赖 PyAV。需要「按画面变化选帧」
时用 ``--scene``，那条路径才需要下载视频。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .bilibili import API, HEADERS, BiliError
from .frames import KeyFrame

_SPRITE_TIMEOUT = 30.0


@dataclass(frozen=True)
class Storyboard:
    sprite_url: str
    columns: int
    rows: int
    cell_width: int
    cell_height: int
    timestamps: list[int]

    @property
    def cells(self) -> int:
        return self.columns * self.rows


def fetch_storyboard(
    bvid: str, page: int = 1, *, client: httpx.Client | None = None
) -> Storyboard:
    """取某分P 的雪碧图信息。"""
    owns_client = client is None
    http = client or httpx.Client(headers=HEADERS, timeout=_SPRITE_TIMEOUT)
    try:
        response = http.get(
            f"{API}/x/player/videoshot",
            params={"bvid": bvid, "index": page},
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
    finally:
        if owns_client:
            http.close()

    code = payload.get("code", 0)
    if code:
        raise BiliError(f"取缩略图失败 code={code}: {payload.get('message', '未知错误')}")

    data = payload.get("data") or {}
    images = data.get("image") or []
    if not images:
        raise BiliError("这个视频没有缩略图（可能是直播回放或刚发布）。")

    url = str(images[0])
    if url.startswith("//"):
        url = "https:" + url

    columns = int(data.get("img_x_len") or 10)
    rows = int(data.get("img_y_len") or 10)
    cell_w = int(data.get("img_x_size") or 160)
    cell_h = int(data.get("img_y_size") or 90)
    timestamps = [int(value) for value in (data.get("index") or [])]

    return Storyboard(
        sprite_url=url,
        columns=max(columns, 1),
        rows=max(rows, 1),
        cell_width=max(cell_w, 1),
        cell_height=max(cell_h, 1),
        timestamps=timestamps,
    )


def choose_cells(total: int, count: int) -> list[int]:
    """在 0..total-1 里均匀挑出 count 个格子编号。"""
    if total <= 0 or count <= 0:
        return []
    count = min(count, total)
    step = total / count
    return sorted({int(index * step) for index in range(count)})


def save_frames(
    board: Storyboard,
    outdir: Path,
    *,
    count: int = 8,
    duration: float | None = None,
    client: httpx.Client | None = None,
) -> list[KeyFrame]:
    """下载雪碧图，挑「画面变化最大」的格子并裁剪成 JPEG。

    B 站返回的 ``index`` 有时只有十几个时间点，和雪碧图的格子数并不对应；这时
    按视频时长把时间点均分到每个格子，避免所有帧都标成 00:00。
    选帧也不再等距硬切：先比较相邻格子的画面差异，优先挑变化大的，并保持间距。
    """
    try:
        from PIL import Image, ImageChops, ImageStat  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise BiliError("缺少 Pillow，请先安装：pip install Pillow") from exc

    import io

    owns_client = client is None
    http = client or httpx.Client(headers=HEADERS, timeout=_SPRITE_TIMEOUT)
    try:
        response = http.get(board.sprite_url)
        response.raise_for_status()
        sheet = Image.open(io.BytesIO(response.content)).convert("RGB")
    finally:
        if owns_client:
            http.close()

    cell_w, cell_h = board.cell_width, board.cell_height
    columns = max(1, sheet.width // cell_w)
    rows = max(1, sheet.height // cell_h)
    total = min(columns * rows, board.cells)
    if total <= 0:
        raise BiliError("雪碧图是空的。")

    # B 站有时只给十几个时间点（对应雪碧图最前面的一批格子），有时一个都不给。
    # 前者只在这些格子里挑，后者按视频时长把时间点均分到整张图。
    if 0 < len(board.timestamps) < total:
        active = len(board.timestamps)
        seconds = [float(value) for value in board.timestamps]
    elif len(board.timestamps) >= total:
        active = total
        seconds = [float(value) for value in board.timestamps[:total]]
    elif duration and duration > 0:
        active = total
        seconds = [duration * index / total for index in range(total)]
    else:
        active = total
        seconds = [0.0] * total

    def cell(index: int) -> "Image.Image":
        column, row = index % columns, index // columns
        return sheet.crop(
            (
                column * cell_w,
                row * cell_h,
                (column + 1) * cell_w,
                (row + 1) * cell_h,
            )
        )

    # 缩略图只用来算差异，48x27 足够快。
    thumbs = [cell(index).convert("L").resize((48, 27)) for index in range(active)]

    def difference(left: "Image.Image", right: "Image.Image") -> float:
        diff = ImageChops.difference(left, right)
        histogram = diff.histogram()
        return sum(value * count for value, count in enumerate(histogram)) / (48 * 27)

    def spread(image: "Image.Image") -> float:
        return float(ImageStat.Stat(image).stddev[0])

    scores = [0.0] * active
    for index in range(1, active):
        if spread(thumbs[index]) < 6 or spread(thumbs[index - 1]) < 6:
            scores[index] = 0.0  # 黑屏/纯色不参与
        else:
            scores[index] = difference(thumbs[index], thumbs[index - 1])

    usable = [index for index in range(active) if spread(thumbs[index]) >= 6]
    order = sorted(
        (index for index in range(1, active) if scores[index] > 0),
        key=lambda index: scores[index],
        reverse=True,
    )
    gap = max(1, active // max(count * 3, 1))
    picked: list[int] = []
    for index in order:
        if len(picked) >= count:
            break
        if all(abs(index - other) >= gap for other in picked):
            picked.append(index)
    # 变化都差不多时，只在有画面的格子里等距补，绝不补黑屏。
    if len(picked) < count and usable:
        pool = [index for index in usable if index not in picked]
        step = max(1, len(pool) // max(count - len(picked), 1))
        for index in pool[::step]:
            if index not in picked:
                picked.append(index)
            if len(picked) >= count:
                break
    if len(picked) < count:
        step = active / max(count, 1)
        for value in (int(index * step) for index in range(count)):
            if value not in picked:
                picked.append(value)
            if len(picked) >= count:
                break
    picked = sorted(picked[:count])

    outdir.mkdir(parents=True, exist_ok=True)
    frames: list[KeyFrame] = []
    for order, index in enumerate(picked, start=1):
        column, row = index % columns, index // columns
        box = (
            column * cell_w,
            row * cell_h,
            (column + 1) * cell_w,
            (row + 1) * cell_h,
        )
        if box[2] > sheet.width or box[3] > sheet.height:
            continue
        value = seconds[index]
        name = f"{order:02d}_{int(value // 60):02d}-{int(value % 60):02d}.jpg"
        path = outdir / name
        sheet.crop(box).save(path, quality=85, optimize=True)
        frames.append(KeyFrame(seconds=value, score=scores[index], path=path))

    return frames


def storyboard_frames(
    bvid: str,
    page: int,
    outdir: Path,
    *,
    count: int = 8,
    duration: float | None = None,
) -> list[KeyFrame]:
    """一步到位：取信息 → 下载 → 挑帧裁剪。"""
    board = fetch_storyboard(bvid, page)
    return save_frames(board, outdir, count=count, duration=duration)
