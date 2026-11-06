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
from .bilibili import BilibiliClient, BiliError, VideoMeta
from .frames import FrameError, KeyFrame, extract_keyframes
from .media import MediaError, hf_endpoint, transcribe_video
from .note import NoteOptions, build_note, filename
from .search import BilibiliSearch
from .storyboard import storyboard_frames


def _force_utf8_output() -> None:
    """Windows 控制台默认是 GBK（代码页 936），中文会乱码。

    统一把控制台输出代码页和 Python 的流编码改成 UTF-8。Python 3.15 起默认就是
    UTF-8，但在那之前、以及打包成 exe 之后，必须显式设置。
    """
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:  # noqa: BLE001 - 没有控制台时忽略
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


_force_utf8_output()

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
    console.print(f"vid2note {__version__}")


@app.command()
def login() -> None:
    """扫码登录 B 站，打印可复用的 Cookie。"""
    import time as _time  # noqa: PLC0415

    from .login import LoginError, generate, poll  # noqa: PLC0415

    try:
        qr = generate()
    except LoginError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from exc

    console.print("用 B 站手机客户端扫码，或打开：")
    console.print(qr["url"])
    try:
        import qrcode  # noqa: PLC0415

        code = qrcode.QRCode(border=1)
        code.add_data(qr["url"])
        code.make()
        code.print_ascii(invert=True)
    except Exception:  # noqa: BLE001 - 终端里画不出来就只给链接
        pass

    last = ""
    while True:
        try:
            result = poll(qr["key"])
        except LoginError as exc:
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(EXIT_ERROR) from exc
        status = result.get("status", "")
        message = result.get("message", "")
        if message and status != last:
            console.print(message)
        last = status
        if status == "ok":
            user = result.get("user") or {}
            if user.get("name"):
                console.print(f"登录成功：{user['name']}")
            console.print("\nCookie（传给 --cookie 或设 VID2NOTE_COOKIE）：")
            console.print(result["cookie"])
            return
        if status in ("expired", "error"):
            raise typer.Exit(EXIT_ERROR)
        _time.sleep(2)


def _progress_runner(
    engine: str,
    meta: VideoMeta,
    page_no: int,
    model: str,
    *,
    use_cache: bool,
    endpoint: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    asr_model: str | None = None,
):
    """带进度条地跑一遍「下载音频 → 下载模型 → 本地转写」。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=err,
        transient=True,
    ) as progress:
        task = progress.add_task("准备中…", total=None)
        phase = {"text": "准备中…"}

        def on_status(text: str) -> None:
            phase["text"] = text
            progress.update(task, description=text)

        def on_progress(done: float, total: float) -> None:
            progress.update(
                task, description=phase["text"], total=total, completed=done
            )

        if engine == "vosk":
            from .asr import transcribe_video as vosk_transcribe

            return vosk_transcribe(
                meta,
                page_no,
                model=model,
                on_progress=on_progress,
                on_status=on_status,
            )
        if engine in ("cloud", "gemini", "whisper-api"):
            from .cloud_asr import transcribe_video as cloud_transcribe

            return cloud_transcribe(
                meta,
                page_no,
                provider=provider or engine,
                api_key=api_key,
                base_url=base_url,
                model=asr_model,
                use_cache=use_cache,
                on_progress=on_progress,
                on_status=on_status,
            )
        return transcribe_video(
            meta,
            page_no,
            model_size=model,
            use_cache=use_cache,
            on_progress=on_progress,
            on_status=on_status,
            endpoint=endpoint,
        )


def _extract_frames(
    meta: VideoMeta,
    page_no: int,
    destination: Path,
    count: int,
    video_path: Path | None = None,
    *,
    scene: bool = False,
) -> list[KeyFrame]:
    """把关键帧导出到笔记旁边的 ``<笔记名>_frames/`` 目录。

    默认走雪碧图：只下载一张拼图再裁剪，不碰视频。``--scene`` 或传入本地文件时，
    才下载视频做画面变化检测。
    """
    outdir = destination.parent / f"{destination.stem}_frames"

    if video_path is not None and not video_path.exists():
        raise FrameError(f"找不到本地视频：{video_path}")

    if scene or video_path is not None:
        with console.status("正在分析画面…" if video_path else "正在下载并分析画面…"):
            return extract_keyframes(
                meta, page_no, outdir, max_frames=count, video_path=video_path
            )

    with console.status("正在取缩略帧…"):
        return storyboard_frames(meta.bvid, page_no, outdir, count=count, duration=meta.duration)


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
        False, "--whisper", "-w", help="没有字幕时用 whisper 在本机转写（需要 [whisper] 依赖）"
    ),
    vosk: bool = typer.Option(
        False, "--vosk", help="没有字幕时用 Vosk 小模型转写（42 MB，需要 [vosk] 依赖）"
    ),
    cloud: bool = typer.Option(
        False, "--cloud", help="没有字幕时用云端转写（Gemini / OpenAI 兼容 Whisper，需要 API Key）"
    ),
    dsh: bool = typer.Option(
        False,
        "--dsh",
        help="没有字幕时用 DSH 本地语音识别（插件宿主注入 VID2NOTE_STT_URL 后可用，无需 Key）",
    ),
    asr_provider: str = typer.Option(
        "auto", "--asr-provider", help="cloud 提供方：auto / gemini / whisper"
    ),
    asr_key: str = typer.Option(
        None,
        "--asr-key",
        help="转写 API Key；也可设 GEMINI_API_KEY / OPENAI_API_KEY / VID2NOTE_ASR_KEY",
    ),
    asr_base: str = typer.Option(
        None, "--asr-base", help="OpenAI 兼容转写接口的 base URL，默认 https://api.openai.com/v1"
    ),
    asr_model: str = typer.Option(
        None, "--asr-model", help="转写模型，如 gemini-2.5-flash / whisper-1"
    ),
    model: str = typer.Option(
        "small", "--model", help="whisper 模型：tiny/base/small/medium/large-v3"
    ),
    channel: str = typer.Option(
        "auto",
        "--channel",
        help="whisper 模型下载渠道：auto / official / mirror",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="不读也不写转写缓存"),
    cookie: str = typer.Option(
        None,
        "--cookie",
        help="B 站 Cookie（SESSDATA=...），用于读取登录后才能拿到的字幕；也可设 VID2NOTE_COOKIE",
    ),
    delay: float = typer.Option(
        0.0, "--delay", min=0.0, help="两次接口请求之间等待的秒数，批量处理时降低频率"
    ),
    frames: int = typer.Option(
        6, "--frames", min=0, max=30, help="抽取关键帧的数量，默认 6，0 表示不抽"
    ),
    video: Path = typer.Option(
        None, "--video", help="用本地视频文件抽帧，而不是从网上下载"
    ),
    scene: bool = typer.Option(
        False,
        "--scene",
        help="按画面变化选帧（需下载视频，需 [scene] 依赖）；默认用 B 站现成的缩略图",
    ),
) -> None:
    """抓取一个视频，生成 Markdown 笔记。"""
    page_no = page
    try:
        with BilibiliClient(cookie=cookie) as client:
            video_id = client.resolve(target)
            page_no = page or video_id.page
            meta = client.view(video_id)
            if page_no < 1 or page_no > len(meta.pages):
                err.print(f"[red]这个视频只有 {len(meta.pages)} 个分P。[/red]")
                raise typer.Exit(EXIT_ERROR)
            current = meta.pages[page_no - 1]
            if delay > 0:
                # 批量循环时用：把两次接口请求之间拉开，别把对方接口打爆。
                time.sleep(delay)
            subtitle = client.subtitles(meta.bvid, current.cid, meta.aid)
    except BiliError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from exc
    except Exception as exc:  # 网络层
        err.print(f"[red]请求失败：{exc}[/red]")
        raise typer.Exit(EXIT_ERROR) from exc

    cues = subtitle[1] if subtitle else None
    lang = subtitle[0] if subtitle else "none"
    transcribed = False

    if cues is None and vosk:
        from .asr import AsrError

        try:
            lang, cues = _progress_runner(
                "vosk", meta, page_no, "vosk-cn", use_cache=False
            )
            transcribed = True
        except AsrError as exc:
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(EXIT_MISSING_DEPS) from exc

    if cues is None and whisper:
        try:
            lang, cues = _progress_runner(
                "whisper",
                meta,
                page_no,
                model,
                use_cache=not no_cache,
                endpoint=hf_endpoint(channel),
            )
            transcribed = True
        except MediaError as exc:
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(EXIT_MISSING_DEPS) from exc

    if cues is None and (cloud or dsh):
        from .cloud_asr import CloudAsrError

        try:
            lang, cues = _progress_runner(
                "cloud",
                meta,
                page_no,
                "",
                use_cache=not no_cache,
                provider="dsh" if dsh else asr_provider,
                api_key=asr_key,
                base_url=asr_base,
                asr_model=asr_model,
            )
            transcribed = True
        except CloudAsrError as exc:
            err.print(f"[red]云端转写失败：{exc}[/red]")
            raise typer.Exit(EXIT_MISSING_DEPS) from exc

    if stdout and frames:
        err.print("[yellow]--stdout 只输出文本，已跳过关键帧图片。[/yellow]")
        frames = 0

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
            shots = _extract_frames(
                meta, page_no, destination, frames, video, scene=scene
            )
        except (FrameError, BiliError, OSError) as exc:
            # 关键帧是锦上添花，拿不到也照常写笔记。
            err.print(f"[yellow]跳过关键帧：{exc}[/yellow]")
            shots = []
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
    console.print("[dim]抓取其中一条：vid2note fetch <BV 号>[/dim]")


@app.command()
def gui(
    app_window: bool = typer.Option(
        False, "--app", help="用 Edge 的应用窗口打开（浏览器已在运行时可能失效）"
    ),
    tk: bool = typer.Option(False, "--tk", help="用 tkinter 窗口（最轻的备选方案）"),
    port: int = typer.Option(0, "--port", help="监听端口，0 表示自动选择"),
) -> None:
    """打开图形界面（浏览器标签页）。

    要「双击就能用的桌面应用」，用打包出来的 ``vidnote-app.exe``：
    那是 WinForms + WebView2 的原生窗口，不经过浏览器。
    """
    if tk:
        from .gui_native import main as tk_main

        tk_main()
        return

    from .gui import serve as serve_web

    serve_web(port=port, app_window=app_window)


@app.command("serve-ui")
def serve_ui(
    port: int = typer.Option(0, "--port", help="监听端口，0 表示自动选择"),
) -> None:
    """只启动界面后端，不打开浏览器（供桌面外壳调用）。"""
    from .gui import serve as serve_web

    serve_web(port=port, open_browser=False)


@app.command()
def serve() -> None:
    """以 MCP server 模式运行（stdio），给 Claude Code / Codex / Cursor 用。"""
    try:
        from .mcp_server import run
    except ImportError:
        if getattr(sys, "frozen", False):
            err.print(
                "[red]这个 exe 是核心版，没有内置 MCP 依赖。[/red]\n"
                "用 pip 安装完整版后运行：pip install 'vid2note[mcp]' && vid2note serve"
            )
        else:
            err.print("[red]缺少依赖：pip install 'vid2note[mcp]'[/red]")
        raise typer.Exit(EXIT_ERROR) from None
    run()


if __name__ == "__main__":
    sys.exit(app())
