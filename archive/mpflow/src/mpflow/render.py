"""Markdown -> WeChat-ready HTML.

WeChat strips ``<style>`` blocks and external stylesheets, so every rule has to
be inlined on the element itself. That is the whole reason this module exists:
the Markdown is easy, the inlining is the annoying part.

The theme is a plain dict so contributors can add one without touching the
renderer.
"""

from __future__ import annotations

import html as html_lib
import re

from markdown_it import MarkdownIt

THEME: dict[str, str] = {
    "h1": "font-size:22px;font-weight:700;color:#1a1a1a;margin:32px 0 16px;line-height:1.4;",
    "h2": "font-size:19px;font-weight:700;color:#1a1a1a;margin:28px 0 14px;line-height:1.4;"
    "padding-left:10px;border-left:4px solid #07c160;",
    "h3": "font-size:17px;font-weight:600;color:#1a1a1a;margin:24px 0 12px;line-height:1.4;",
    "p": "font-size:16px;line-height:1.75;color:#3f3f3f;margin:0 0 16px;letter-spacing:0.3px;",
    "blockquote": "margin:16px 0;padding:12px 16px;background:#f7f7f7;border-left:4px solid #d0d0d0;"
    "color:#666;font-size:15px;line-height:1.7;",
    "ul": "margin:0 0 16px;padding-left:22px;",
    "ol": "margin:0 0 16px;padding-left:22px;",
    "li": "font-size:16px;line-height:1.75;color:#3f3f3f;margin:6px 0;",
    "pre": "margin:16px 0;padding:14px 16px;background:#f6f8fa;border-radius:6px;"
    "overflow-x:auto;font-size:13px;line-height:1.6;",
    "code_block": "font-family:Menlo,Consolas,monospace;font-size:13px;color:#24292f;"
    "background:none;padding:0;white-space:pre;",
    "code_inline": "font-family:Menlo,Consolas,monospace;font-size:14px;color:#d63384;"
    "background:#f6f8fa;padding:2px 5px;border-radius:3px;",
    "img": "max-width:100%;height:auto;display:block;margin:16px auto;border-radius:4px;",
    "a": "color:#07c160;text-decoration:none;border-bottom:1px solid #b7ebc9;",
    "table": "width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;",
    "th": "border:1px solid #e0e0e0;background:#f7f7f7;padding:8px 10px;font-weight:600;"
    "text-align:left;color:#1a1a1a;",
    "td": "border:1px solid #e0e0e0;padding:8px 10px;color:#3f3f3f;",
    "hr": "border:0;border-top:1px solid #e8e8e8;margin:28px 0;",
    "strong": "font-weight:600;color:#1a1a1a;",
}

_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "ul", "ol", "li", "hr")

_PRE_RE = re.compile(r"<pre><code(?: class=\"language-([^\"]+)\")?>", re.IGNORECASE)
_IMG_RE = re.compile(r'<img\s+src="([^"]*)"\s+alt="([^"]*)"\s*/?>', re.IGNORECASE)
_LINK_RE = re.compile(r"<a\s+href=", re.IGNORECASE)


def _md() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": True, "linkify": False}).enable(
        ["table", "strikethrough"]
    )


def inline_styles(rendered: str, theme: dict[str, str] | None = None) -> str:
    """Attach the theme's CSS to every element WeChat renders."""
    t = {**THEME, **(theme or {})}

    for tag in _BLOCK_TAGS:
        rendered = rendered.replace(f"<{tag}>", f'<{tag} style="{t[tag]}">')

    # Fenced code: <pre><code class="language-x"> ... </code></pre>
    rendered = _PRE_RE.sub(
        lambda m: (
            f'<pre style="{t["pre"]}"><code'
            + (f' class="language-{m.group(1)}"' if m.group(1) else "")
            + f' style="{t["code_block"]}">'
        ),
        rendered,
    )
    # Whatever <code> is left is inline code.
    rendered = rendered.replace("<code>", f'<code style="{t["code_inline"]}">')

    rendered = _IMG_RE.sub(lambda m: f'<img src="{m.group(1)}" alt="{m.group(2)}" style="{t["img"]}" />', rendered)

    # These carry attributes already (href, colspan, ...), so append the style.
    for tag in ("a", "table", "th", "td"):
        rendered = re.sub(
            rf"<{tag}(\s[^>]*)?>",
            lambda m, tag=tag: f'<{tag}{m.group(1) or ""} style="{t[tag]}">',
            rendered,
        )
    return rendered


def render_markdown(text: str, theme: dict[str, str] | None = None) -> str:
    """Render Markdown to a WeChat-safe HTML fragment."""
    return inline_styles(_md().render(text), theme)


def plain_text(text: str) -> str:
    """Strip Markdown syntax, for building the digest."""
    rendered = _md().render(text)
    stripped = re.sub(r"<[^>]+>", "", rendered)
    return html_lib.unescape(stripped)


def extract_title(text: str, fallback: str = "未命名文章") -> str:
    """First level-1 heading, else the first non-empty line."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped and not stripped.startswith(("```", "---", ">")):
            return stripped[:60]
    return fallback


def build_digest(text: str, limit: int = 120) -> str:
    """WeChat caps the digest at 120 characters."""
    flattened = " ".join(plain_text(text).split())
    return flattened[:limit]
