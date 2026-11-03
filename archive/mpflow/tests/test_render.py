from mpflow.render import (
    build_digest,
    extract_title,
    render_markdown,
)

SAMPLE = """# 标题

正文第一段，带 **加粗** 和 `行内代码`。

## 小节

> 引用一句话。

```python
print("hi")
```

| 列 A | 列 B |
| --- | --- |
| 1 | 2 |

![图](https://example.com/a.png)

[链接](https://example.com)
"""


def test_headings_and_paragraphs_are_inlined() -> None:
    html = render_markdown(SAMPLE)
    assert '<h1 style="' in html
    assert '<h2 style="' in html
    assert '<p style="' in html
    assert "<style>" not in html


def test_fenced_code_is_not_double_styled() -> None:
    html = render_markdown(SAMPLE)
    assert html.count('class="language-python"') == 1
    assert html.count("<pre style=") == 1
    assert html.count('style="font-family:Menlo') == 2  # block + inline


def test_inline_code_and_links() -> None:
    html = render_markdown(SAMPLE)
    assert "background:#f6f8fa" in html
    assert 'href="https://example.com"' in html
    assert html.count("border-bottom") == 1


def test_table_and_image() -> None:
    html = render_markdown(SAMPLE)
    assert "<table style=" in html
    assert "<th " in html
    assert "max-width:100%" in html


def test_extract_title_prefers_h1() -> None:
    assert extract_title(SAMPLE) == "标题"
    assert extract_title("没有标题的正文\n第二行") == "没有标题的正文"


def test_digest_is_capped_at_120() -> None:
    digest = build_digest("长" * 500)
    assert len(digest) == 120


def test_digest_strips_markup() -> None:
    digest = build_digest("**加粗** 和 `代码`")
    assert "*" not in digest
    assert "`" not in digest
