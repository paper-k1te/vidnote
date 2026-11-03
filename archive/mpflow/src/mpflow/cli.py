"""Command line interface."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .client import WeChatClient, WeChatError
from .config import ConfigError, Credentials
from .render import build_digest, extract_title, render_markdown

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="把 Markdown 变成公众号草稿，再发布。",
)
console = Console()


def _read(path: Path) -> str:
    if not path.exists():
        console.print(f"[red]找不到文件：{path}[/red]")
        raise typer.Exit(1)
    return path.read_text(encoding="utf-8")


def _client() -> WeChatClient:
    try:
        creds = Credentials.from_env()
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    return WeChatClient(creds.appid, creds.secret)


@app.command()
def version() -> None:
    """打印版本号。"""
    console.print(f"mpflow {__version__}")


@app.command()
def status() -> None:
    """检查凭证是否配置、能否拿到 access_token。"""
    if not Credentials.is_configured():
        console.print("[yellow]未配置 MP_APPID / MP_SECRET[/yellow]")
        raise typer.Exit(1)
    with _client() as client:
        try:
            token = client.access_token()
        except WeChatError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
    console.print(f"[green]OK[/green] access_token 已获取（{token[:8]}…）")


@app.command()
def preview(
    file: Path = typer.Argument(..., help="Markdown 文件"),
    output: Path = typer.Option(None, "--output", "-o", help="输出 HTML 路径"),
) -> None:
    """本地渲染，不调用任何接口。"""
    text = _read(file)
    html = render_markdown(text)
    document = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{extract_title(text)}</title></head>"
        "<body style='max-width:680px;margin:0 auto;padding:24px;background:#fff;'>"
        f"{html}</body></html>"
    )
    target = output or file.with_suffix(".html")
    target.write_text(document, encoding="utf-8")
    console.print(f"[green]已生成[/green] {target}")


@app.command()
def draft(
    file: Path = typer.Argument(..., help="Markdown 文件"),
    thumb: Path = typer.Option(None, "--thumb", help="封面图路径（公众号要求必须有封面）"),
    title: str = typer.Option(None, "--title", help="标题，默认取一级标题"),
    author: str = typer.Option("", "--author", help="作者名"),
    digest: str = typer.Option(None, "--digest", help="摘要，默认取正文前 120 字"),
) -> None:
    """创建草稿，返回 media_id。"""
    text = _read(file)
    html = render_markdown(text)
    article: dict[str, object] = {
        "title": title or extract_title(text),
        "author": author,
        "digest": digest if digest is not None else build_digest(text),
        "content": html,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    if thumb:
        if not thumb.exists():
            console.print(f"[red]找不到封面图：{thumb}[/red]")
            raise typer.Exit(1)
        with _client() as client:
            try:
                article["thumb_media_id"] = client.upload_thumb(thumb)
                media_id = client.add_draft([article])
            except WeChatError as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(1) from exc
    else:
        console.print("[yellow]没有提供 --thumb，公众号草稿需要封面，发布会失败。[/yellow]")
        with _client() as client:
            try:
                media_id = client.add_draft([article])
            except WeChatError as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(1) from exc

    console.print(f"[green]草稿已创建[/green] media_id={media_id}")
    console.print("确认无误后运行：", f"mpflow publish {media_id}")


@app.command()
def publish(
    media_id: str = typer.Argument(..., help="draft 命令返回的 media_id"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
) -> None:
    """发布草稿（不可撤销，需要确认）。"""
    if not yes:
        confirmed = typer.confirm("发布会推送给所有订阅者，且无法撤回。继续？", default=False)
        if not confirmed:
            console.print("已取消。")
            raise typer.Exit(0)
    with _client() as client:
        try:
            publish_id = client.publish(media_id)
        except WeChatError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
    console.print(f"[green]已提交发布[/green] publish_id={publish_id}")


@app.command()
def serve() -> None:
    """以 MCP server 模式运行（stdio），给 Claude Code / Codex / Cursor 用。"""
    try:
        from .mcp_server import run
    except ImportError:
        console.print("[red]缺少依赖：pip install 'mpflow[mcp]'[/red]")
        raise typer.Exit(1) from None
    run()


if __name__ == "__main__":
    sys.exit(app())
