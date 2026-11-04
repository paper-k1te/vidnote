"""图形界面：本地 HTTP 服务 + 系统的 Edge/Chrome「应用窗口」。

为什么不用 WebView 库：pywebview 在 Python 3.13 上装不上（依赖 proxy_tools 没有
wheel），而 Electron/Tauri 会把体积推到几十上百 MB。

``msedge --app=<url>`` 是 Windows 自带的「无地址栏应用窗口」模式：外观和独立桌面
应用一样，体积零增加，WebView2 内核本身就是系统组件。

进程生命周期：界面每 3 秒 ping 一次 ``/api/ping``，窗口关掉后心跳停止，服务在
超时后自动退出，不会留下一个后台进程。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .bilibili import BilibiliClient, BiliError, parse_video_id
from .note import NoteOptions, build_note, filename
from .search import BilibiliSearch
from .storyboard import storyboard_frames

IDLE_EXIT_SECONDS = 12.0

INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>vidnote</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #0a0d11;
    --panel: #11161d;
    --panel-2: #0d1218;
    --line: #1e2833;
    --text: #e8eef6;
    --muted: #7d8b9c;
    --accent: #00b3ff;
    --accent-2: #07c160;
    --danger: #ff5c5c;
    --radius: 14px;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0; background: radial-gradient(1200px 600px at 20% -10%, #10202b 0%, var(--bg) 55%);
    color: var(--text); font: 14px/1.5 "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
    display: flex; flex-direction: column; overflow: hidden;
  }
  header {
    display: flex; align-items: center; gap: 12px; padding: 14px 22px;
    border-bottom: 1px solid var(--line); background: rgba(13, 18, 24, .8);
    backdrop-filter: blur(8px); -webkit-app-region: drag; user-select: none;
  }
  header .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--accent-2); box-shadow: 0 0 12px var(--accent-2); }
  header h1 { margin: 0; font-size: 17px; letter-spacing: .2px; }
  header .tag { color: var(--muted); font-size: 12.5px; }
  header .ver { margin-left: auto; color: var(--muted); font-size: 12px; }
  main { flex: 1; display: grid; grid-template-columns: 420px 1fr; gap: 16px; padding: 16px 22px 20px; min-height: 0; }
  @media (max-width: 980px) { main { grid-template-columns: 1fr; overflow: auto; } }
  .col { display: flex; flex-direction: column; gap: 16px; min-height: 0; }
  .card {
    background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%);
    border: 1px solid var(--line); border-radius: var(--radius); padding: 16px;
    box-shadow: 0 12px 30px rgba(0,0,0,.25);
  }
  .card.grow { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .card h2 {
    margin: 0 0 12px; font-size: 12px; font-weight: 600; letter-spacing: .12em;
    text-transform: uppercase; color: var(--muted);
  }
  label { display: block; font-size: 12px; color: var(--muted); margin: 12px 0 6px; }
  label:first-of-type { margin-top: 0; }
  input {
    width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid #263241;
    background: #0a0f15; color: var(--text); font-size: 13.5px; transition: border-color .15s, box-shadow .15s;
  }
  input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(0,179,255,.12); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  button {
    border: 0; border-radius: 10px; padding: 10px 16px; font-size: 13.5px; font-weight: 600;
    cursor: pointer; transition: transform .06s, filter .15s, background .15s;
    background: linear-gradient(180deg, #21c1ff, #0096d6); color: #04121a;
  }
  button:hover { filter: brightness(1.08); }
  button:active { transform: translateY(1px); }
  button:disabled { opacity: .45; cursor: default; transform: none; }
  button.ghost { background: #17202a; color: #c7d4e2; font-weight: 500; border: 1px solid #243040; }
  button.ghost:hover { background: #1d2833; }
  .row { display: flex; gap: 8px; margin-top: 16px; }
  .row button { flex: 1; }
  ul { list-style: none; margin: 12px 0 0; padding: 0; overflow: auto; min-height: 0; flex: 1; }
  li {
    padding: 9px 10px; border-radius: 10px; cursor: pointer; border: 1px solid transparent;
    transition: background .12s, border-color .12s;
  }
  li:hover { background: #131c26; border-color: #223040; }
  li b { display: block; font-size: 13px; font-weight: 500; margin-bottom: 2px; }
  li small { color: var(--muted); font-size: 11.5px; }
  .preview-wrap { position: relative; flex: 1; min-height: 0; }
  #preview {
    height: 100%; overflow: auto; padding: 18px 20px; border-radius: 12px;
    background: #080c11; border: 1px solid #1a242f; font-size: 13.5px; line-height: 1.75;
  }
  #preview h1 { font-size: 21px; margin: 0 0 14px; }
  #preview h2 { font-size: 16px; margin: 22px 0 10px; padding-left: 10px; border-left: 3px solid var(--accent-2); }
  #preview p { margin: 0 0 12px; color: #c8d4e2; }
  #preview table { border-collapse: collapse; width: 100%; margin: 0 0 14px; }
  #preview th, #preview td { border: 1px solid #223040; padding: 6px 10px; text-align: left; font-size: 12.5px; }
  #preview th { background: #101820; color: var(--muted); font-weight: 600; }
  #preview a { color: var(--accent); text-decoration: none; }
  #preview a:hover { text-decoration: underline; }
  #preview code { background: #101820; padding: 1px 5px; border-radius: 4px; color: #ffb3d1; font-size: 12.5px; }
  #preview img { max-width: 100%; border-radius: 8px; display: block; margin: 8px 0; }
  #preview .empty { color: var(--muted); }
  .toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .toolbar .path { color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
  .toast {
    position: fixed; right: 20px; bottom: 20px; padding: 11px 16px; border-radius: 10px;
    background: #141c26; border: 1px solid #24303d; color: var(--text); font-size: 13px;
    box-shadow: 0 10px 30px rgba(0,0,0,.4); opacity: 0; transform: translateY(8px);
    transition: opacity .2s, transform .2s; pointer-events: none; max-width: 420px;
  }
  .toast.show { opacity: 1; transform: translateY(0); }
  .toast.ok { border-color: #1d5c3a; }
  .toast.err { border-color: #5c1d1d; color: #ffb4b4; }
  .spinner {
    width: 13px; height: 13px; border: 2px solid rgba(255,255,255,.25); border-top-color: #04121a;
    border-radius: 50%; display: inline-block; animation: spin .7s linear infinite; vertical-align: -2px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<header>
  <span class="dot"></span>
  <h1>vidnote</h1>
  <span class="tag">B 站视频 → 带时间戳的 Markdown 笔记</span>
  <span class="ver">v__VERSION__</span>
</header>

<main>
  <div class="col">
    <section class="card">
      <h2>抓取</h2>
      <label>视频链接 / BV 号 / av 号</label>
      <input id="target" placeholder="BV1xx411c7mD 或 https://www.bilibili.com/video/...">
      <div class="grid2">
        <div>
          <label>分P</label>
          <input id="page" type="number" min="1" value="1">
        </div>
        <div>
          <label>关键帧数量</label>
          <input id="frames" type="number" min="0" max="30" value="0">
        </div>
      </div>
      <label>输出目录（留空 = 当前目录）</label>
      <input id="outdir" placeholder="例如 D:\\notes\\bilibili">
      <div class="row">
        <button id="go">生成笔记</button>
      </div>
    </section>

    <section class="card grow">
      <h2>搜索</h2>
      <input id="q" placeholder="输入关键词后回车">
      <ul id="results"><li style="cursor:default"><small>还没有搜索结果</small></li></ul>
    </section>
  </div>

  <section class="card grow">
    <h2>预览</h2>
    <div class="toolbar">
      <span class="path" id="path">生成后显示文件位置</span>
      <button class="ghost" id="copy" disabled>复制 Markdown</button>
      <button class="ghost" id="reveal" disabled>打开文件</button>
    </div>
    <div class="preview-wrap">
      <div id="preview"><p class="empty">填入链接并点击「生成笔记」，这里会显示渲染后的结果。</p></div>
    </div>
  </section>
</main>

<div class="toast" id="toast"></div>

<script>
const $ = (id) => document.getElementById(id);
let lastNote = "";
let lastPath = "";

function toast(message, kind) {
  const el = $("toast");
  el.textContent = message;
  el.className = "toast show " + (kind || "");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.className = "toast " + (kind || ""); }, 3200);
}

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || ("HTTP " + response.status));
  return data;
}

function busy(button, on, label) {
  button.disabled = on;
  button.innerHTML = on ? '<span class="spinner"></span> ' + label : label;
}

// 极简 Markdown 渲染，够看就行：标题、粗体、代码、链接、图片、表格、列表。
function renderMarkdown(md) {
  const lines = md.split("\n");
  let html = "", inTable = false, inList = false;
  const inline = (s) => s
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2">')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^\|/.test(line)) {
      const cells = line.split("|").slice(1, -1).map((c) => c.trim());
      if (/^[-: ]+$/.test(cells.join(""))) continue;
      if (!inTable) { html += "<table>"; inTable = true; }
      const tag = html.endsWith("<table>") ? "th" : "td";
      html += "<tr>" + cells.map((c) => `<${tag}>${inline(c)}</${tag}>`).join("") + "</tr>";
      continue;
    } else if (inTable) { html += "</table>"; inTable = false; }
    if (/^### /.test(line)) html += "<h3>" + inline(line.slice(4)) + "</h3>";
    else if (/^## /.test(line)) html += "<h2>" + inline(line.slice(3)) + "</h2>";
    else if (/^# /.test(line)) html += "<h1>" + inline(line.slice(2)) + "</h1>";
    else if (/^[-*] /.test(line)) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += "<li>" + inline(line.slice(2)) + "</li>";
      continue;
    } else if (inList) { html += "</ul>"; inList = false; }
    if (/^---$/.test(line)) html += "<hr>";
    else if (line && !/^### |^## |^# /.test(line) && !/^[-*] /.test(line)) html += "<p>" + inline(line) + "</p>";
  }
  if (inTable) html += "</table>";
  if (inList) html += "</ul>";
  return html;
}

$("q").addEventListener("keydown", (event) => { if (event.key === "Enter") doSearch(); });
$("target").addEventListener("keydown", (event) => { if (event.key === "Enter") doFetch(); });
$("go").onclick = doFetch;

async function doSearch() {
  const q = $("q").value.trim();
  if (!q) return toast("先输入关键词", "err");
  const button = $("q");
  button.disabled = true;
  try {
    const data = await api("/api/search?q=" + encodeURIComponent(q) + "&limit=10");
    const list = $("results");
    list.innerHTML = "";
    if (!data.results.length) list.innerHTML = '<li style="cursor:default"><small>没有找到结果</small></li>';
    for (const item of data.results) {
      const li = document.createElement("li");
      li.innerHTML = "<b></b><small></small>";
      li.querySelector("b").textContent = item.title;
      li.querySelector("small").textContent = `${item.author} · ${item.duration} · ${item.play.toLocaleString()} 播放`;
      li.onclick = () => { $("target").value = item.bvid; toast("已填入 " + item.bvid, "ok"); };
      list.appendChild(li);
    }
    toast(`找到 ${data.results.length} 个结果`, "ok");
  } catch (error) { toast(error.message, "err"); }
  finally { button.disabled = false; }
}

async function doFetch() {
  const target = $("target").value.trim();
  if (!target) return toast("先填一个视频链接或 BV 号", "err");
  busy($("go"), true, "抓取中…");
  try {
    const data = await api("/api/fetch", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        target,
        page: parseInt($("page").value || "1", 10),
        frames: parseInt($("frames").value || "0", 10),
        outdir: $("outdir").value.trim(),
      }),
    });
    lastNote = data.note;
    lastPath = data.path;
    $("preview").innerHTML = renderMarkdown(data.note);
    $("path").textContent = data.path;
    $("copy").disabled = false;
    $("reveal").disabled = false;
    toast(data.frames ? `完成，含 ${data.frames} 张关键帧` : "完成", "ok");
  } catch (error) { toast(error.message, "err"); }
  finally { busy($("go"), false, "生成笔记"); }
}

$("copy").onclick = async () => {
  if (!lastNote) return;
  try { await navigator.clipboard.writeText(lastNote); toast("已复制", "ok"); }
  catch { toast("复制失败，请手动选择", "err"); }
};

$("reveal").onclick = async () => {
  if (!lastPath) return;
  try {
    await api("/api/reveal", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path: lastPath}),
    });
  } catch (error) { toast(error.message, "err"); }
};

// 心跳：窗口关掉后服务端会自动退出，不留后台进程。
setInterval(() => { fetch("/api/ping").catch(() => {}); }, 3000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = f"vidnote/{__version__}"
    last_ping = time.time()
    seen_ping = False

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(
        self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            page = INDEX_HTML.replace("__VERSION__", __version__)
            self._send(HTTPStatus.OK, page.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self._json({"ok": True, "version": __version__})
            return
        if parsed.path == "/api/ping":
            Handler.last_ping = time.time()
            Handler.seen_ping = True
            self._json({"ok": True})
            return
        if parsed.path == "/api/search":
            query = parse_qs(parsed.query)
            keyword = (query.get("q") or [""])[0]
            limit = int((query.get("limit") or ["8"])[0])
            self._json(search_videos(keyword, limit))
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/fetch":
            Handler.last_ping = time.time()
            self._json(fetch_video(self._body()))
            return
        if parsed.path == "/api/reveal":
            self._json(reveal(self._body().get("path", "")))
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def search_videos(keyword: str, limit: int = 8) -> dict[str, Any]:
    try:
        with BilibiliSearch() as client:
            results = client.search(keyword, limit=limit)
    except BiliError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"请求失败：{exc}"}
    return {
        "results": [
            {
                "bvid": item.bvid,
                "title": item.title,
                "author": item.author,
                "duration": item.duration,
                "play": item.play,
            }
            for item in results
        ]
    }


def fetch_video(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(payload.get("target", "")).strip()
    page = int(payload.get("page") or 1)
    frames = int(payload.get("frames") or 0)
    outdir = str(payload.get("outdir", "")).strip()

    try:
        video_id = parse_video_id(target)
    except BiliError as exc:
        return {"error": str(exc)}

    try:
        with BilibiliClient() as client:
            meta = client.view(video_id)
            if page < 1 or page > len(meta.pages):
                return {"error": f"这个视频只有 {len(meta.pages)} 个分P。"}
            subtitle = client.subtitles(meta.bvid, meta.pages[page - 1].cid)
    except BiliError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"请求失败：{exc}"}

    cues = subtitle[1] if subtitle else None
    lang = subtitle[0] if subtitle else "none"

    directory = Path(outdir) if outdir else Path.cwd()
    destination = directory / filename(meta)

    keyframes: list[tuple[float, str]] = []
    if frames:
        try:
            out = destination.parent / f"{destination.stem}_frames"
            shots = storyboard_frames(meta.bvid, page, out, count=frames)
            keyframes = [
                (shot.seconds, shot.relative_to(destination.parent)) for shot in shots
            ]
        except Exception as exc:  # noqa: BLE001
            return {"error": f"取关键帧失败：{exc}"}

    note = build_note(
        meta,
        cues,
        options=NoteOptions(page=page),
        subtitle_lang=lang,
        frames=keyframes,
    )

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(note, encoding="utf-8")
    except OSError as exc:
        return {"error": f"写入文件失败：{exc}"}

    return {"note": note, "path": str(destination), "frames": len(keyframes)}


def reveal(path: str) -> dict[str, Any]:
    if not path:
        return {"error": "没有可打开的文件"}
    target = Path(path)
    if not target.exists():
        return {"error": f"文件不存在：{path}"}
    try:
        if os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606
        else:
            import sys

            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(target)])  # noqa: S603
    except OSError as exc:
        return {"error": f"打开失败：{exc}"}
    return {"ok": True}


def find_app_browser() -> str | None:
    """找一个能开 ``--app`` 窗口的 Chromium 系浏览器。"""
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def open_app_window(url: str) -> subprocess.Popen[bytes] | None:
    """用 Edge/Chrome 的 --app 模式打开一个独立窗口，返回进程句柄。

    任何一步失败都返回 None（调用方会退回普通浏览器），绝不抛异常——
    界面打不开不应该让服务端也跟着挂掉。
    """
    browser = find_app_browser()
    if not browser:
        return None

    args = [
        browser,
        f"--app={url}",
        "--window-size=1180,820",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
    ]
    # 不指定 --user-data-dir：用用户自己的配置目录。临时 profile 会触发 Edge 的
    # 首次运行/同步引导，窗口先显示一片空白甚至被弹窗盖住。

    try:
        return subprocess.Popen(args, close_fds=True)  # noqa: S603
    except OSError:
        return None


def _message_box(text: str, title: str = "vidnote") -> None:
    """没有控制台时（GUI 版 exe）用系统弹窗提示错误。"""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    except Exception:  # noqa: BLE001
        pass


def _watchdog(server: ThreadingHTTPServer, timeout: float = 20.0) -> None:
    """界面关掉后自动退出，避免留下后台进程。

    页面每 3 秒 ping 一次；窗口关了心跳就断。等第一次心跳之后才开始计时，
    否则浏览器还没加载完就被判死。
    """
    started = time.time()
    while True:
        time.sleep(2)
        now = time.time()
        if Handler.seen_ping:
            if now - Handler.last_ping > timeout:
                _log("心跳超时，界面可能已关闭，退出")
                server.shutdown()
                return
        elif now - started > 120:
            _log("120 秒内没有收到心跳，退出")
            server.shutdown()
            return


def _log(message: str) -> None:
    """界面版 exe 没有控制台，诊断信息写文件；终端里同时也打印。"""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    try:
        log_path = Path(tempfile.gettempdir()) / "vidnote-ui.log"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    try:
        if sys.stdout is not None:
            print(message)
    except Exception:  # noqa: BLE001 - 没有 stdout 时忽略
        pass


def serve(*, port: int = 0, open_browser: bool = True, app_window: bool = False) -> None:
    """启动服务并打开界面，直到窗口关闭或 Ctrl+C。

    生命周期跟着窗口进程走：不再用心跳猜——页面没加载完就退出，会变成
    「拒绝连接」。窗口进程结束，服务才结束。
    """
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        _log(f"绑定端口失败：{exc}")
        _message_box(f"端口被占用，无法启动界面：{exc}")
        raise

    actual = server.server_address[1]
    url = f"http://127.0.0.1:{actual}/"
    _log(f"启动 {__version__}，监听 {url}")

    window: subprocess.Popen[bytes] | None = None
    if open_browser:
        if app_window:
            try:
                window = open_app_window(url)
            except Exception as exc:  # noqa: BLE001 - 界面失败不能拖垮服务端
                _log(f"打开应用窗口失败：{exc}")
                window = None
        if window is None:
            _log("退回默认浏览器")
            webbrowser.open(url)
        else:
            _log(f"已请求打开应用窗口（pid={window.pid}）")
            # 注意：Edge 已经在运行时，新进程只会把请求转交给已有实例然后立即退出。
            # 所以不能用「进程退出」来判断窗口关闭，只能靠页面心跳。

    threading.Thread(target=_watchdog, args=(server,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("收到 Ctrl+C，退出")
    except Exception as exc:  # noqa: BLE001
        _log(f"服务异常：{exc}")
        raise
    finally:
        server.server_close()
        if window is not None and window.poll() is None:
            window.terminate()
