"""MCP server exposing mpflow to coding agents.

Run with::

    mpflow serve

The tools are deliberately narrow: rendering is free, creating a draft is
cheap, publishing always requires an explicit call from a human-approved step.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .client import WeChatClient, WeChatError
from .config import ConfigError, Credentials
from .render import build_digest, extract_title, render_markdown

mcp = FastMCP("mpflow")


@mcp.tool()
def render_preview(markdown: str, title: str | None = None) -> str:
    """把 Markdown 渲染成公众号可用的 HTML（内联样式），不联网、不需要凭证。"""
    return render_markdown(markdown)


@mcp.tool()
def create_draft(
    markdown: str,
    title: str | None = None,
    thumb_path: str | None = None,
    author: str = "",
) -> str:
    """在公众号草稿箱创建草稿，返回 media_id。封面图是公众号的硬性要求。"""
    try:
        creds = Credentials.from_env()
    except ConfigError as exc:
        return f"配置错误：{exc}"

    article: dict[str, object] = {
        "title": title or extract_title(markdown),
        "author": author,
        "digest": build_digest(markdown),
        "content": render_markdown(markdown),
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    with WeChatClient(creds.appid, creds.secret) as client:
        try:
            if thumb_path:
                article["thumb_media_id"] = client.upload_thumb(Path(thumb_path))
            media_id = client.add_draft([article])
        except WeChatError as exc:
            return f"创建失败：{exc}"
        except OSError as exc:
            return f"读取封面图失败：{exc}"
    return f"草稿已创建，media_id={media_id}。确认后调用 publish_draft。"


@mcp.tool()
def publish_draft(media_id: str) -> str:
    """发布指定草稿。会推送给全部订阅者且不可撤回，调用前必须得到用户明确同意。"""
    try:
        creds = Credentials.from_env()
    except ConfigError as exc:
        return f"配置错误：{exc}"
    with WeChatClient(creds.appid, creds.secret) as client:
        try:
            publish_id = client.publish(media_id)
        except WeChatError as exc:
            return f"发布失败：{exc}"
    return f"已提交发布，publish_id={publish_id}。"


@mcp.tool()
def session_status() -> str:
    """检查凭证是否可用（能否拿到 access_token）。"""
    if not Credentials.is_configured():
        return "未配置 MP_APPID / MP_SECRET。"
    try:
        creds = Credentials.from_env()
    except ConfigError as exc:
        return str(exc)
    with WeChatClient(creds.appid, creds.secret) as client:
        try:
            client.access_token()
        except WeChatError as exc:
            return f"不可用：{exc}"
    return "可用。"


def run() -> None:
    mcp.run()
