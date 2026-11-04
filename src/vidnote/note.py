"""把抓到的元数据和字幕组装成一篇 Markdown 笔记。

笔记的目标是「归档」而不是「摘要」：保留原始字幕、来源链接、抓取时间，
让它可以被 Dataview 之类的工具检索，也能脱离任何软件直接读。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import yaml

from .bilibili import Cue, VideoMeta

_ILLEGAL = re.compile(r'[\\/:*?"<>|\n\r\t]+')


def fmt_ts(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def ts_link(url: str, seconds: float) -> str:
    """B 站的 ?t= 参数接受秒数，点开会从该时刻播放。"""
    return f"[{fmt_ts(seconds)}]({url}?t={int(seconds)})"


def slugify(title: str, limit: int = 40) -> str:
    cleaned = _ILLEGAL.sub(" ", title).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:limit].strip("-") or "untitled"


def filename(meta: VideoMeta, *, when: date | None = None) -> str:
    day = when or date.today()
    return f"{day.isoformat()}_{slugify(meta.title)}_{meta.bvid}.md"


@dataclass(frozen=True)
class NoteOptions:
    source: str | None = None
    include_desc: bool = True
    page: int = 1
    fetched: date | None = None


def build_note(
    meta: VideoMeta,
    cues: list[Cue] | None,
    *,
    options: NoteOptions | None = None,
    subtitle_lang: str = "zh",
    frames: list[tuple[float, str]] | None = None,
) -> str:
    opts = options or NoteOptions()
    url = meta.url
    current = meta.pages[min(opts.page, len(meta.pages)) - 1] if meta.pages else None

    front: dict[str, object] = {
        "title": meta.title,
        "platform": "bilibili",
        "bvid": meta.bvid,
        "url": url,
        "owner": meta.owner,
        "duration": fmt_ts(meta.duration),
        "published": meta.pubdate.date().isoformat(),
        "fetched": (opts.fetched or date.today()).isoformat(),
        "language": subtitle_lang,
        "subtitle": "available" if cues else "none",
        "tags": ["bilibili", "vidnote"],
    }
    if opts.page > 1 and current:
        front["page"] = f"P{current.index} {current.title}"
    if opts.source:
        front["source_project"] = opts.source
    if meta.tags:
        front["bili_tags"] = meta.tags[:8]

    lines: list[str] = [
        "---",
        yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip(),
        "---",
        "",
        f"# {meta.title}",
        "",
        "## 视频信息",
        "",
        "| 项目 | 内容 |",
        "| --- | --- |",
        f"| 链接 | {url} |",
        f"| UP 主 | {meta.owner} |",
        f"| 时长 | {fmt_ts(meta.duration)} |",
        f"| 发布 | {meta.pubdate.date().isoformat()} |",
        f"| 抓取 | {(opts.fetched or date.today()).isoformat()} |",
    ]
    if current and len(meta.pages) > 1:
        lines.append(f"| 分P | P{current.index} {current.title} |")
    lines.append("")

    if opts.include_desc and meta.desc:
        lines += ["## 简介", "", meta.desc.strip(), ""]

    if len(meta.pages) > 1:
        lines += ["## 分P", ""]
        for page in meta.pages:
            marker = "**" if current and page.index == current.index else ""
            lines.append(f"- {marker}P{page.index} {page.title}（{fmt_ts(page.duration)}）{marker}")
        lines.append("")

    if frames:
        lines += ["## 关键帧", ""]
        for seconds, relative in frames:
            lines.append(f"**{ts_link(url, seconds)}**")
            lines.append("")
            lines.append(f"![{fmt_ts(seconds)}]({relative})")
            lines.append("")

    lines += ["## 字幕", ""]
    if not cues:
        lines += [
            "> 这个视频没有可用字幕。装了 `faster-whisper` 和 `yt-dlp` 后，",
            "> 可以用 `vidnote fetch --whisper` 在本地转写。",
            "",
        ]
    else:
        for cue in cues:
            lines.append(f"**{ts_link(url, cue.start)}** {cue.text}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
