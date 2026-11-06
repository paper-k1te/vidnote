"""简介清理的回归测试。"""

from __future__ import annotations

from vid2note.note import clean_description


def test_removes_parenthesized_link() -> None:
    text = "(https://www.bilibili.com/video/BV1wsQzYDEE3?t=38) 家里没有的呢，可以用现成的气泡水。"
    assert clean_description(text) == "家里没有的呢，可以用现成的气泡水。"


def test_removes_bare_link() -> None:
    assert clean_description("配方在 https://example.com/a 里") == "配方在 里"


def test_keeps_normal_text() -> None:
    assert clean_description("第一行\n\n第二行") == "第一行\n\n第二行"
