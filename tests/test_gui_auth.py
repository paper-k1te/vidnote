"""界面 API 的会话校验测试。"""

from __future__ import annotations

from vid2note.gui import api_authorized


def test_public_paths() -> None:
    assert api_authorized("/", "", "t")
    assert api_authorized("/api/health", "", "t")
    assert api_authorized("/api/ping", "", "t")


def test_api_requires_matching_token() -> None:
    assert not api_authorized("/api/fetch", "", "t")
    assert not api_authorized("/api/fetch", "wrong", "t")
    assert api_authorized("/api/fetch", "t", "t")
    assert not api_authorized("/api/deps/install", "", "t")
