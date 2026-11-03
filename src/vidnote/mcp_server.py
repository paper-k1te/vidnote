"""MCP server：让 agent 直接抓视频、拿笔记。

运行：``vidnote serve``
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .bilibili import BilibiliClient, BiliError, parse_video_id
from .media import MediaError, transcribe_video
from .note import NoteOptions, build_note

mcp = FastMCP("vidnote")


@mcp.tool()
def fetch_note(
    target: str,
    page: int = 1,
    include_desc: bool = True,
    transcribe: bool = False,
) -> str:
    """把 B 站视频链接/BV 号转成带时间戳的 Markdown 笔记，直接返回文本。

    transcribe=True 时，如果没有现成字幕，会在本机用 whisper 转写（较慢）。
    """
    try:
        video_id = parse_video_id(target)
    except BiliError as exc:
        return f"输入无法解析：{exc}"

    try:
        with BilibiliClient() as client:
            meta = client.view(video_id)
            index = min(max(page, 1), len(meta.pages))
            subtitle = client.subtitles(meta.bvid, meta.pages[index - 1].cid)
    except BiliError as exc:
        return f"抓取失败：{exc}"
    except Exception as exc:  # 网络层
        return f"网络错误：{exc}"

    cues = subtitle[1] if subtitle else None
    lang = subtitle[0] if subtitle else "none"

    if cues is None and transcribe:
        try:
            lang, cues = transcribe_video(meta, index)
        except MediaError as exc:
            return f"本地转写失败：{exc}"

    return build_note(
        meta,
        cues,
        options=NoteOptions(include_desc=include_desc, page=index),
        subtitle_lang=lang,
    )


def run() -> None:
    mcp.run()
