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


def _nearest_cells(board: Storyboard, times: list[float]) -> list[int]:
    """把时刻换成最接近的缩略图格子，去重后按时间排序。"""
    if not board.timestamps:
        return []
    cells: set[int] = set()
    for moment in times:
        index = min(
            range(len(board.timestamps)),
            key=lambda i: abs(board.timestamps[i] - moment),
        )
        cells.add(index)
    return sorted(cells)


def save_frames(
    board: Storyboard,
    outdir: Path,
    *,
    count: int = 8,
    times: list[float] | None = None,
    client: httpx.Client | None = None,
) -> list[KeyFrame]:
    """下载雪碧图，按格子裁剪并保存为 JPEG。"""
    try:
        from PIL import Image  # noqa: PLC0415
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

    picked = _nearest_cells(board, times) if times else []
    if not picked:
        picked = choose_cells(
            min(board.cells, len(board.timestamps) or board.cells), count
        )
    outdir.mkdir(parents=True, exist_ok=True)

    frames: list[KeyFrame] = []
    for order, cell_index in enumerate(picked, start=1):
        column = cell_index % board.columns
        row = cell_index // board.columns
        box = (
            column * board.cell_width,
            row * board.cell_height,
            (column + 1) * board.cell_width,
            (row + 1) * board.cell_height,
        )
        if box[2] > sheet.width or box[3] > sheet.height:
            continue

        seconds = float(board.timestamps[cell_index]) if cell_index < len(board.timestamps) else 0.0
        name = f"{order:02d}_{int(seconds // 60):02d}-{int(seconds % 60):02d}.jpg"
        path = outdir / name
        sheet.crop(box).save(path, quality=85, optimize=True)
        frames.append(KeyFrame(seconds=seconds, score=0.0, path=path))

    return frames


def storyboard_frames(
    bvid: str,
    page: int,
    outdir: Path,
    *,
    count: int = 8,
    times: list[float] | None = None,
) -> list[KeyFrame]:
    """一步到位：取信息 → 下载 → 裁剪。"""
    board = fetch_storyboard(bvid, page)
    return save_frames(board, outdir, count=count, times=times)
