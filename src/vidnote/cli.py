"""命令行入口。

退出码约定（和常见 CLI 保持一致，方便脚本判断）：
    0  成功
    1  网络/接口/输入错误
    2  参数错误
    3  目标文件已存在且没有加 --force
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__
from .bilibili import BilibiliClient, BiliError, Cue, VideoMeta, parse_video_id
from .frames import FrameError, KeyFrame, extract_keyframes
from .media import MediaError, transcribe_video
from .note import NoteOptions, build_note, filename
from .search import BilibiliSearch

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="把 B 站视频变成带时间戳的 Markdown 笔记。",
)
console = Console()
err = Console(stderr=True)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_MISSING_DEPS = 2
EXIT_EXISTS = 3


@app.command()
def version() -> None:
    """打印版本号。"""
    console.print(f"vidnote {__version__}")


def _transcribe(
    meta: VideoMeta, page_no: int, model: str, *, use_cache: bool
) -> tuple[str, list[Cue]]:
    """带进度条地跑一遍「下载音频 → 本地转写」。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=err,
        transient=True,
    ) as progress:
        task = progress.add_task("正在下载音频…", total=None)

        def on_progress(done: float, total: float) -> None:
            progress.update(
                task, description="正在本地转写…", total=total, completed=done
            )

        return transcribe_video(
            meta,
            page_no,
            model_size=model,
            use_cache=use_cache,
            on_progress=on_progress,
        )


def _extract_frames(
    meta: VideoMeta,
    page_no: int,
    destination: Path,
    count: int,
    video_path: Path | None = None,
) -> list[KeyFrame]:
    """把关键帧导出到笔记旁边的 ``<笔记名>_frames/`` 目录。"""
    if video_path is not None and not video_path.exists():
        raise FrameError(f"找不到本地视频：{video_path}")
    outdir = destination.parent / f"{destination.stem}_frames"
    with console.status("正在分析画面…" if video_path else "正在下载并分析画面…"):
        return extract_keyframes(
            meta, page_no, outdir, max_frames=count, video_path=video_path
        )


@app.command()
def fetch(
    target: str = typer.Argument(..., help="B 站链接、BV 号或 av 号"),
    output: Path = typer.Option(None, "--output", "-o", help="输出到指定文件"),
    output_dir: Path = typer.Option(None, "--dir", "-d", help="输出到指定目录"),
    page: int = typer.Option(0, "--page", "-p", help="分P 序号，默认跟链接里的 ?p="),
    source: str = typer.Option(None, "--source", "-s", help="标记这条笔记的来源项目"),
    no_desc: bool = typer.Option(False, "--no-desc", help="不包含视频简介"),
    stdout: bool = typer.Option(False, "--stdout", help="打印到终端，不写文件"),
    force: bool = typer.Option(False, "--force", "-f", help="覆盖已存在的文件"),
    whisper: bool = typer.Option(
        False, "--whisper", "-w", help="没有字幕时，在本机转写音频（需要 [whisper] 依赖）"
    ),
    model: str = typer.Option("small", "--model", help="转写模型：tiny/base/small/medium/large-v3"),
    no_cache: bool = typer.Option(False, "--no-cache", help="不读也不写转写缓存"),
    delay: float = typer.Option(
        0.0, "--delay", min=0.0, help="两次接口请求之间等待的秒数，批量处理时降低频率"
    ),
    frames: int = typer.Option(
        0, "--frames", min=0, max=30, help="抽取关键帧的数量，0 表示不抽（需要 [frames] 依赖）"
    ),
    video: Path = typer.Option(
        None, "--video", help="用本地视频文件抽帧，而不是从网上下载"
    ),
) -> None:
    """抓取一个视频，生成 Markdown 笔记。"""
    try:
        video_id = parse_video_id(target)
    except BiliError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from exc

    page_no = page or video_id.page

    try:
        with BilibiliClient() as client:
            meta = client.view(video_id)
            if page_no < 1 or page_no > len(meta.pages):
                err.print(f"[red]这个视频只有 {len(meta.pages)} 个分P。[/red]")
                raise typer.Exit(EXIT_ERROR)
            current = meta.pages[page_no - 1]
            if delay > 0:
                # 批量循环时用：把两次接口请求之间拉开，别把对方接口打爆。
                time.sleep(delay)
            subtitle = client.subtitles(meta.bvid, current.cid)
    except BiliError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from exc
    except Exception as exc:  # 网络层
        err.print(f"[red]请求失败：{exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from exc

    cues = subtitle[1] if subtitle else None
    lang = subtitle[0] if subtitle else "none"
    transcribed = False

    if cues is None and whisper:
        try:
            lang, cues = _transcribe(meta, page_no, model, use_cache=not no_cache)
            transcribed = True
        except MediaError as exc:
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(EXIT_MISSING_DEPS) from exc

    if stdout and frames:
        err.print("[red]抓关键帧需要写文件，不能和 --stdout 一起用。[/red]")
        raise typer.Exit(EXIT_MISSING_DEPS)

    if stdout:
        text = build_note(
            meta,
            cues,
            options=NoteOptions(source=source, include_desc=not no_desc, page=page_no),
            subtitle_lang=lang,
        )
        sys.stdout.write(text)
        raise typer.Exit(EXIT_OK)

    directory = output_dir or Path.cwd()
    destination = output or (directory / filename(meta))
    if destination.exists() and not force:
        err.print(
            f"[yellow]文件已存在：{destination}[/yellow]\n"
            "加 --force 覆盖，或换一个 --output。"
        )
        raise typer.Exit(EXIT_EXISTS)

    keyframes: list[tuple[float, str]] = []
    if frames:
        try:
            shots = _extract_frames(meta, page_no, destination, frames, video)
        except FrameError as exc:
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(EXIT_MISSING_DEPS) from exc
        keyframes = [(shot.seconds, shot.relative_to(destination.parent)) for shot in shots]

    text = build_note(
        meta,
        cues,
        options=NoteOptions(source=source, include_desc=not no_desc, page=page_no),
        subtitle_lang=lang,
        frames=keyframes,
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    # 先写临时文件再替换，避免中途失败留下半个文件。
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(destination)

    if transcribed:
        status = "本地转写"
    elif cues:
        status = "有字幕"
    else:
        status = "无字幕"
    extra = f"，关键帧 {len(keyframes)} 张" if keyframes else ""
    console.print(
        f"[green]已生成[/green] {destination}  （{status}，{len(cues or [])} 条{extra}）"
    )


@app.command()
def search(
    keyword: str = typer.Argument(..., help="搜索关键词"),
    limit: int = typer.Option(10, "--limit", "-n", min=1, max=50, help="返回条数"),
    as_json: bool = typer.Option(False, "--json", help="输出 JSON，方便脚本处理"),
) -> None:
    """按关键词搜索 B 站视频，拿到 BV 号后再用 fetch 抓取。"""
    try:
        with BilibiliSearch() as client:
            results = client.search(keyword, limit=limit)
    except BiliError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from exc
    except Exception as exc:  # 网络层
        err.print(f"[red]请求失败：{exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from exc

    if as_json:
        sys.stdout.write(
            json.dumps(
                [
                    {
                        "bvid": item.bvid,
                        "title": item.title,
                        "author": item.author,
                        "duration": item.duration,
                        "play": item.play,
                        "url": item.url,
                    }
                    for item in results
                ],
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        raise typer.Exit(EXIT_OK)

    if not results:
        console.print("[yellow]没有找到相关视频。[/yellow]")
        raise typer.Exit(EXIT_OK)

    table = Table(show_header=True, header_style="bold")
    table.add_column("BV 号", style="cyan", no_wrap=True)
    table.add_column("标题", overflow="fold")
    table.add_column("UP 主", style="dim")
    table.add_column("时长", justify="right")
    table.add_column("播放", justify="right")
    for item in results:
        table.add_row(item.bvid, item.title, item.author, item.duration, f"{item.play:,}")
    console.print(table)
    console.print("[dim]抓取其中一条：vidnote fetch <BV 号>[/dim]")


@app.command()
def serve() -> None:
    """以 MCP server 模式运行（stdio），给 Claude Code / Codex / Cursor 用。"""
    try:
        from .mcp_server import run
    except ImportError:
        err.print("[red]缺少依赖：pip install 'vidnote[mcp]'[/red]")
        raise typer.Exit(EXIT_ERROR) from None
    run()


if __name__ == "__main__":
    sys.exit(app())
