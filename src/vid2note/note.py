"""把抓到的元数据和字幕组装成一篇 Markdown 笔记。

笔记的目标是「归档」而不是「摘要」：保留原始字幕、来源链接、抓取时间、
关键帧，让它可以被 Dataview 之类的工具检索，也能脱离任何软件直接读。

关键帧不单独堆在文末，而是插在对应时间段的字幕后面——读到哪里，画面就在哪里。
"""

from __future__ import annotations

import re
from bisect import bisect_right
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


def fmt_count(value: int) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f} 亿"
    if value >= 10_000:
        return f"{value / 10_000:.1f} 万"
    return f"{value:,}"


_URL_IN_TEXT = re.compile(r"[（(]\s*https?://[^\s()（）]+?\s*[)）]|https?://[^\s()（）]+")


def clean_description(text: str) -> str:
    """去掉简介里的裸链接和括号链接。

    B 站简介里常出现 ``(https://www.bilibili.com/video/BV...)`` 这种「想做成
    超链接但没做成」的残句，直接删掉比留在笔记里干净。
    """
    cleaned = _URL_IN_TEXT.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


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


def _frame_image(seconds: float, relative: str) -> list[str]:
    # 标题里的括号会出现在目录名里，用尖括号包住路径，Markdown 才不会被截断。
    return [f"![关键帧 {fmt_ts(seconds)}](<{relative}>)", ""]


def _frames_by_cue(
    cues: list[Cue], frames: list[tuple[float, str]]
) -> dict[int, list[tuple[float, str]]]:
    """把每张关键帧归到它前面最近的那条字幕。

    关键帧时间落在两条字幕之间时，属于正在讲的那一段；早于第一条的归给第一条，
    晚于最后一条的归给最后一条，保证不会有帧被丢掉。
    """
    starts = [cue.start for cue in cues]
    buckets: dict[int, list[tuple[float, str]]] = {}
    for seconds, relative in sorted(frames):
        index = clamp(bisect_right(starts, seconds) - 1, 0, len(cues) - 1)
        buckets.setdefault(index, []).append((seconds, relative))
    return buckets


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _copyright_text(value: int) -> str:
    return {1: "原创", 2: "转载"}.get(value, "")


def _subtitle_state(meta: VideoMeta, cues: list[Cue] | None) -> str:
    if cues:
        return "available"
    if meta.subtitle_tracks:
        return "locked" if any(track.locked for track in meta.subtitle_tracks) else "listed"
    return "none"


def _subtitle_notice(meta: VideoMeta) -> list[str]:
    tracks = meta.subtitle_tracks
    if tracks:
        labels = "、".join(track.label for track in tracks)
        if any(track.locked for track in tracks):
            return [
                f"> 这个视频有字幕（{labels}），但 B 站要求登录后才能读取。",
                "> 用 `--cookie` 或环境变量 `VIDNOTE_COOKIE` 带上 SESSDATA 后重试。",
                "",
            ]
        return [
            f"> 接口列出了字幕（{labels}），但没有返回正文；可能需要登录信息。",
            "",
        ]
    return [
        "> 这个视频没有可用字幕。装了 `faster-whisper` 和 `yt-dlp` 后，",
        "> 可以用 `vid2note fetch --whisper` 在本地转写。",
        "",
    ]


def _season_url(season) -> str:
    if season.mid:
        return (
            f"https://space.bilibili.com/{season.mid}"
            f"/channel/collectiondetail?sid={season.id}"
        )
    return ""


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
    stats = meta.stats

    front: dict[str, object] = {
        "title": meta.title,
        "platform": "bilibili",
        "bvid": meta.bvid,
        "aid": meta.aid,
        "url": url,
        "owner": meta.owner,
        "duration": fmt_ts(meta.duration),
        "duration_seconds": meta.duration,
        "published": meta.pubdate.date().isoformat(),
        "published_at": meta.pubdate.isoformat(),
        "fetched": (opts.fetched or date.today()).isoformat(),
        "language": subtitle_lang,
        "subtitle": _subtitle_state(meta, cues),
        "tags": ["bilibili", "vid2note"],
    }
    if opts.page > 1 and current:
        front["page"] = f"P{current.index} {current.title}"
    if opts.source:
        front["source_project"] = opts.source
    if meta.tags:
        front["bili_tags"] = meta.tags[:12]
    if meta.owner_mid:
        front["owner_mid"] = meta.owner_mid
    if meta.tname:
        front["category"] = meta.tname
    if meta.cover:
        front["cover"] = meta.cover
    if _copyright_text(meta.copyright):
        front["copyright"] = _copyright_text(meta.copyright)
    if meta.dimension:
        front["dimension"] = meta.dimension
    if meta.subtitle_tracks:
        front["subtitle_languages"] = [
            track.label for track in meta.subtitle_tracks
        ]
    if len(meta.staff) > 1:
        front["staff"] = [
            {"mid": person.mid, "name": person.name, "title": person.title}
            for person in meta.staff
        ]
    if meta.season:
        front["season_id"] = meta.season.id
        front["season_title"] = meta.season.title
        front["season_episodes"] = len(meta.season.episodes)
    if frames:
        front["keyframes"] = len(frames)
    if any(
        (
            stats.view,
            stats.danmaku,
            stats.reply,
            stats.favorite,
            stats.coin,
            stats.share,
            stats.like,
        )
    ):
        front["stats"] = {
            "view": stats.view,
            "danmaku": stats.danmaku,
            "reply": stats.reply,
            "favorite": stats.favorite,
            "coin": stats.coin,
            "share": stats.share,
            "like": stats.like,
        }

    owner_cell = f"[{meta.owner}]({meta.owner_url})" if meta.owner_url else meta.owner
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
        f"| UP 主 | {owner_cell} |",
        f"| 时长 | {fmt_ts(meta.duration)} |",
        f"| 发布 | {meta.pubdate.strftime('%Y-%m-%d %H:%M')} |",
        f"| 抓取 | {(opts.fetched or date.today()).isoformat()} |",
    ]
    if meta.tname:
        lines.append(f"| 分区 | {meta.tname} |")
    if _copyright_text(meta.copyright):
        lines.append(f"| 类型 | {_copyright_text(meta.copyright)} |")
    if meta.dimension:
        lines.append(f"| 画质 | {meta.dimension} |")
    if current and len(meta.pages) > 1:
        lines.append(f"| 分P | P{current.index} {current.title} |")
    if cues:
        subtitle_cell = "有"
    elif meta.subtitle_tracks:
        subtitle_cell = (
            "有（需登录）"
            if any(track.locked for track in meta.subtitle_tracks)
            else "有（未返回内容）"
        )
    else:
        subtitle_cell = "无"
    lines.append(f"| 字幕 | {subtitle_cell} |")
    if meta.cover:
        lines.append(f"| 封面 | [原图]({meta.cover}) |")
    if len(meta.staff) > 1:
        team = "、".join(
            f"{person.name}（{person.title}）" if person.title else person.name
            for person in meta.staff
        )
        lines.append(f"| 制作团队 | {team} |")
    if meta.season:
        season_url = _season_url(meta.season)
        label = (
            f"[{meta.season.title}]({season_url})"
            if season_url
            else meta.season.title
        )
        lines.append(f"| 合集 | {label}（{len(meta.season.episodes)} 集） |")
    if stats.view:
        lines.append(f"| 播放 | {fmt_count(stats.view)} |")
    if stats.like:
        lines.append(f"| 点赞 | {fmt_count(stats.like)} |")
    if stats.coin:
        lines.append(f"| 投币 | {fmt_count(stats.coin)} |")
    if stats.favorite:
        lines.append(f"| 收藏 | {fmt_count(stats.favorite)} |")
    if stats.danmaku:
        lines.append(f"| 弹幕 | {fmt_count(stats.danmaku)} |")
    if stats.reply:
        lines.append(f"| 评论 | {fmt_count(stats.reply)} |")
    if meta.tags:
        lines.append(f"| 标签 | {'、'.join(meta.tags[:12])} |")
    lines.append("")

    description = clean_description(meta.desc) if meta.desc else ""
    if opts.include_desc and description:
        lines += ["## 简介", "", description, ""]

    if len(meta.pages) > 1:
        lines += ["## 分P", ""]
        for page in meta.pages:
            marker = "▶ " if current and page.index == current.index else ""
            lines.append(
                f"- {marker}[P{page.index} {page.title}]({url}?p={page.index})"
                f"（{fmt_ts(page.duration)}）"
            )
        lines.append("")

    if meta.season and meta.season.episodes:
        season = meta.season
        lines += ["## 合集", ""]
        season_url = _season_url(season)
        label = f"[{season.title}]({season_url})" if season_url else season.title
        lines.append(f"{label}（共 {len(season.episodes)} 集）")
        lines.append("")
        for section in season.sections:
            if len(season.sections) > 1 and section.title:
                lines += [f"### {section.title}", ""]
            for episode in section.episodes:
                marker = "▶ " if episode.bvid == meta.bvid else ""
                suffix = f"?p={episode.page}" if episode.page > 1 else ""
                lines.append(
                    f"- {marker}[{episode.title}]({episode.url}{suffix})"
                    f"（{fmt_ts(episode.duration)}）"
                )
            lines.append("")

    if cues:
        lines += ["## 字幕", ""]
        buckets = _frames_by_cue(cues, frames) if frames else {}
        for index, cue in enumerate(cues):
            lines.append(f"{ts_link(url, cue.start)} {cue.text}")
            lines.append("")
            for seconds, relative in buckets.get(index, []):
                lines += _frame_image(seconds, relative)
    elif frames:
        lines += ["## 关键帧", ""]
        for seconds, relative in sorted(frames):
            lines.append(ts_link(url, seconds))
            lines.append("")
            lines += _frame_image(seconds, relative)

    if not cues:
        lines += ["## 字幕", ""]
        lines += _subtitle_notice(meta)

    return "\n".join(lines).rstrip() + "\n"
