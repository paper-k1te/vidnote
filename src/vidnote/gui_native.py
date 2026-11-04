"""原生窗口界面（tkinter）。

不依赖浏览器：输入链接、点按钮、看预览都在一个窗口里完成。tkinter 是 Python
标准库，打包进 exe 只增加几 MB，比内嵌 WebView 干净得多。

耗时操作（网络请求、取缩略图）放在后台线程，结果用 ``root.after`` 回到主线程，
避免窗口卡死。
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any

from . import __version__
from .bilibili import BilibiliClient, BiliError
from .note import NoteOptions, build_note, filename
from .search import BilibiliSearch, SearchResult
from .storyboard import storyboard_frames

PAD = 10
MUTED = "#5d6b7a"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.current_path: Path | None = None
        self.results: list[SearchResult] = []

        root.title(f"vidnote {__version__}")
        root.geometry("980x640")
        root.minsize(820, 520)

        self._build_header()
        self._build_body()
        self._build_status()

    # -- 布局 -------------------------------------------------------------

    def _build_header(self) -> None:
        frame = ttk.Frame(self.root, padding=(PAD, PAD, PAD, 0))
        frame.pack(fill="x")

        ttk.Label(frame, text="vidnote", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(
            frame,
            text="把 B 站视频变成带时间戳的 Markdown 笔记",
            foreground=MUTED,
        ).pack(side="left", padx=(10, 0), pady=(6, 0))

    def _build_body(self) -> None:
        body = ttk.Frame(self.root, padding=PAD)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        form = ttk.LabelFrame(body, text=" 抓取 ", padding=PAD)
        form.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, PAD))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="视频链接 / BV 号").grid(row=0, column=0, sticky="w")
        self.target = ttk.Entry(form)
        self.target.grid(row=0, column=1, columnspan=5, sticky="ew", padx=(8, 0), pady=2)

        ttk.Label(form, text="分P").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.page = tk.StringVar(value="1")
        ttk.Spinbox(form, from_=1, to=999, width=6, textvariable=self.page).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )

        ttk.Label(form, text="关键帧").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(6, 0))
        self.frames = tk.StringVar(value="6")
        ttk.Spinbox(form, from_=0, to=30, width=6, textvariable=self.frames).grid(
            row=1, column=3, sticky="w", padx=(8, 0), pady=(6, 0)
        )

        ttk.Label(form, text="输出目录").grid(
            row=1, column=4, sticky="w", padx=(16, 0), pady=(6, 0)
        )
        self.outdir = ttk.Entry(form, width=28)
        self.outdir.grid(row=1, column=5, sticky="ew", padx=(8, 0), pady=(6, 0))

        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, columnspan=6, sticky="w", pady=(PAD, 0))
        self.fetch_button = ttk.Button(buttons, text="生成笔记", command=self.on_fetch)
        self.fetch_button.pack(side="left")
        self.reveal_button = ttk.Button(
            buttons, text="打开目录", command=self.on_reveal, state="disabled"
        )
        self.reveal_button.pack(side="left", padx=(8, 0))

        # 左：搜索；右：预览
        left = ttk.LabelFrame(body, text=" 搜索 ", padding=PAD)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, PAD))
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        search_row = ttk.Frame(left)
        search_row.grid(row=0, column=0, sticky="ew")
        search_row.columnconfigure(0, weight=1)
        self.keyword = ttk.Entry(search_row)
        self.keyword.grid(row=0, column=0, sticky="ew")
        self.keyword.bind("<Return>", lambda _event: self.on_search())
        self.search_button = ttk.Button(search_row, text="搜索", command=self.on_search)
        self.search_button.grid(row=0, column=1, padx=(8, 0))

        ttk.Label(left, text="点击结果填入 BV 号", foreground=MUTED).grid(
            row=1, column=0, sticky="w", pady=(6, 4)
        )
        self.result_list = tk.Listbox(left, activestyle="none", exportselection=False)
        self.result_list.grid(row=2, column=0, sticky="nsew")
        self.result_list.bind("<<ListboxSelect>>", self.on_pick)

        right = ttk.LabelFrame(body, text=" 预览 ", padding=PAD)
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.preview = tk.Text(
            right, wrap="word", font=("Consolas", 10), state="disabled", padx=8, pady=8
        )
        self.preview.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(right, orient="vertical", command=self.preview.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.preview.configure(yscrollcommand=scroll.set)

    def _build_status(self) -> None:
        self.status = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status, padding=(PAD, 4, PAD, PAD)).pack(
            fill="x", anchor="w"
        )

    # -- 交互 -------------------------------------------------------------

    def set_status(self, text: str) -> None:
        self.status.set(text)

    def run_in_background(self, work, done) -> None:
        """在线程里跑 work，回主线程执行 done(result, error)。"""

        def runner() -> None:
            result, error = None, None
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                error = exc
            self.root.after(0, lambda: done(result, error))

        threading.Thread(target=runner, daemon=True).start()

    def on_search(self) -> None:
        keyword = self.keyword.get().strip()
        if not keyword:
            self.set_status("先输入搜索关键词")
            return
        self.search_button.configure(state="disabled")
        self.set_status(f"搜索「{keyword}」…")

        def work() -> list[SearchResult]:
            with BilibiliSearch() as client:
                return client.search(keyword, limit=10)

        def done(results: Any, error: Exception | None) -> None:
            self.search_button.configure(state="normal")
            if error:
                self.set_status(f"搜索失败：{error}")
                return
            self.results = results
            self.result_list.delete(0, tk.END)
            for item in results:
                self.result_list.insert(tk.END, f"{item.bvid}  {item.title}  ·  {item.author}")
            self.set_status(f"找到 {len(results)} 个结果" if results else "没有找到结果")

        self.run_in_background(work, done)

    def on_pick(self, _event: object) -> None:
        selection = self.result_list.curselection()
        if not selection:
            return
        item = self.results[selection[0]]
        self.target.delete(0, tk.END)
        self.target.insert(0, item.bvid)
        self.set_status(f"已选择 {item.bvid}")

    def on_fetch(self) -> None:
        target = self.target.get().strip()
        if not target:
            self.set_status("先填一个视频链接或 BV 号")
            return
        try:
            page = max(1, int(self.page.get()))
        except ValueError:
            page = 1
        try:
            frames = max(0, min(30, int(self.frames.get())))
        except ValueError:
            frames = 0
        outdir = self.outdir.get().strip()

        self.fetch_button.configure(state="disabled")
        self.set_status("抓取中…")

        def work() -> dict[str, Any]:
            return build_note_file(target, page=page, frames=frames, outdir=outdir)

        def done(result: dict[str, Any] | None, error: Exception | None) -> None:
            self.fetch_button.configure(state="normal")
            if error:
                self.set_status(f"失败：{error}")
                return
            if not result or "error" in result:
                self.set_status(f"失败：{result.get('error') if result else '未知错误'}")
                return
            self.current_path = Path(result["path"])
            self.show_preview(result["note"])
            self.reveal_button.configure(state="normal")
            extra = f"，关键帧 {result['frames']} 张" if result.get("frames") else ""
            self.set_status(f"已保存 {result['path']}{extra}")

        self.run_in_background(work, done)

    def show_preview(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def on_reveal(self) -> None:
        if not self.current_path:
            return
        try:
            if self.current_path.exists():
                import os

                os.startfile(self.current_path)  # type: ignore[attr-defined]  # noqa: S606
        except OSError as exc:
            self.set_status(f"打开失败：{exc}")


def build_note_file(
    target: str, *, page: int = 1, frames: int = 0, outdir: str = ""
) -> dict[str, Any]:
    """抓取 + 生成笔记，返回给界面用的字典。"""
    try:
        with BilibiliClient() as client:
            video_id = client.resolve(target)
            meta = client.view(video_id)
            if page < 1 or page > len(meta.pages):
                return {"error": f"这个视频只有 {len(meta.pages)} 个分P。"}
            subtitle = client.subtitles(meta.bvid, meta.pages[page - 1].cid, meta.aid)
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
            frame_dir = destination.parent / f"{destination.stem}_frames"
            shots = storyboard_frames(meta.bvid, page, frame_dir, count=frames)
            keyframes = [(shot.seconds, shot.relative_to(destination.parent)) for shot in shots]
        except Exception:  # noqa: BLE001 - 关键帧失败不阻塞笔记
            keyframes = []

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


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
