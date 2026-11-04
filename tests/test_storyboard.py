"""雪碧图取帧的测试，不联网。"""

from pathlib import Path

import httpx
import pytest

from vidnote.bilibili import BiliError
from vidnote.frames import KeyFrame
from vidnote.storyboard import (
    Storyboard,
    choose_cells,
    fetch_storyboard,
    save_frames,
)

PIL = pytest.importorskip("PIL.Image")

RESPONSE = {
    "code": 0,
    "data": {
        "image": ["//i0.hdslb.com/bfs/videoshot/1.jpg"],
        "img_x_len": 2,
        "img_y_len": 2,
        "img_x_size": 160,
        "img_y_size": 90,
        "index": [0, 60, 120, 180],
    },
}


def test_choose_cells_spreads_evenly() -> None:
    assert choose_cells(100, 4) == [0, 25, 50, 75]
    assert choose_cells(10, 3) == [0, 3, 6]
    assert choose_cells(0, 5) == []
    assert choose_cells(5, 0) == []


def test_choose_cells_never_exceeds_total() -> None:
    assert choose_cells(3, 10) == [0, 1, 2]


def test_fetch_storyboard_maps_fields() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=RESPONSE))
    with httpx.Client(transport=transport) as client:
        board = fetch_storyboard("BV1", 1, client=client)

    assert board.sprite_url == "https://i0.hdslb.com/bfs/videoshot/1.jpg"
    assert (board.columns, board.rows) == (2, 2)
    assert (board.cell_width, board.cell_height) == (160, 90)
    assert board.timestamps == [0, 60, 120, 180]
    assert board.cells == 4


def test_fetch_storyboard_rejects_missing_image() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"code": 0, "data": {}}))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(BiliError):
            fetch_storyboard("BV1", 1, client=client)


def make_sprite(path: Path) -> None:
    sheet = PIL.new("RGB", (320, 180), (20, 20, 20))
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    for index, color in enumerate(colors):
        column, row = index % 2, index // 2
        box = (column * 160, row * 90, column * 160 + 160, row * 90 + 90)
        sheet.paste(PIL.new("RGB", (160, 90), color), box)
    sheet.save(path, format="JPEG")


def test_save_frames_crops_cells(tmp_path: Path) -> None:
    sprite = tmp_path / "sprite.jpg"
    make_sprite(sprite)
    content = sprite.read_bytes()

    board = Storyboard(
        sprite_url="https://example.com/sprite.jpg",
        columns=2,
        rows=2,
        cell_width=160,
        cell_height=90,
        timestamps=[0, 60, 120, 180],
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=content))
    with httpx.Client(transport=transport) as client:
        frames = save_frames(board, tmp_path / "frames", count=2, client=client)

    assert len(frames) == 2
    assert all(isinstance(frame, KeyFrame) for frame in frames)
    assert [frame.seconds for frame in frames] == [0.0, 120.0]
    for frame in frames:
        assert frame.path.exists()
        with PIL.open(frame.path) as image:
            assert image.size == (160, 90)
