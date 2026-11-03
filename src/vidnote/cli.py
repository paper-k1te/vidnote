"""命令行入口。

退出码约定（和常见 CLI 保持一致，方便脚本判断）：
    0  成功
    1  网络/接口/输入错误
    2  参数错误
    3  目标文件已存在且没有加 --force
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from . import __version__
from .bilibili import BilibiliClient, BiliError, Cue, VideoMeta, parse_video_id
from .media import MediaError, transcribe_video
from .note import NoteOptions, build_note, filename

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
) -> None:
    """抓取一个视频，生成 Markdown 笔记。"""
    try:
        video = parse_video_id(target)
    except BiliError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from exc

    page_no = page or video.page

    try:
        with BilibiliClient() as client:
            meta = client.view(video)
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

    text = build_note(
        meta,
        cues,
        options=NoteOptions(source=source, include_desc=not no_desc, page=page_no),
        subtitle_lang=lang,
    )

    if stdout:
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
    console.print(f"[green]已生成[/green] {destination}  （{status}，{len(cues or [])} 条）")


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
