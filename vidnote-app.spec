# -*- mode: python ; coding: utf-8 -*-
"""桌面版打包配置：核心功能 + 云端转写 + yt-dlp。

默认不再内置 Vosk 模型（省 65 MB），没有字幕时走云端的 Gemini / OpenAI 兼容
Whisper 接口；想离线转写可以 ``pip install 'vid2note[vosk]'`` 后手动选 Vosk。
whisper 的推理引擎（ctranslate2 / onnxruntime / tokenizers 等）同样不打进
exe，第一次要用时由界面单独下载 ``vidnote-whisper-deps-<版本>.zip``。

这是唯一发布的桌面构建；完整版目标已合并进来，不再单独构建。

用法：
    pyinstaller vidnote-app.spec --noconfirm --distpath dist-exe --workpath build-exe
"""

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ["packaging/entry.py"],
    pathex=["src"],
    datas=[
        ("src/vid2note/ui/index.html", "vid2note/ui"),
    ]
    + collect_data_files("srt"),
    hiddenimports=[
        "srt",
        "requests",
        "av",
        "yt_dlp",
        "qrcode",
        "qrcode.image.pil",
        # whisper 用 tqdm.auto。
        "tqdm.auto",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # whisper 依赖改为运行时单独下载
        "faster_whisper",
        "ctranslate2",
        "onnxruntime",
        "tokenizers",
        "huggingface_hub",
        "hf_xet",
        "numpy",
        "pydantic",
        "pydantic_core",
        "httpx2",
        "httpcore2",
        # yt-dlp 的可选网络处理器；B 站下载走 urllib 即可
        "cryptography",
        "OpenSSL",
        "websockets",
        "sqlite3",
        # 与运行无关的东西
        "mcp",
        "tkinter",
        "pytest",
        "setuptools",
        # 桌面窗口由 C# 外壳（WebView2）负责
        "webview",
        "pythonnet",
        "clr_loader",
        "bottle",
        "proxy_tools",
        # Pillow 里用不到的界面/插件部分
        "PIL.ImageQt",
        "PIL.ImageTk",
        "PIL.ImageShow",
        "PIL.ImageGrab",
        "PIL.AvifImagePlugin",
        "PIL.WebPImagePlugin",
        "PIL.ImageCms",
        "PIL.IptcImagePlugin",
        "PIL.FitsImagePlugin",
    ],
    noarchive=False,
)

_DROP_BINARIES = ("PIL\\_avif", "PIL\\_imagingft", "PIL\\_webp", "PIL\\_imagingcms")
a.binaries = [
    item
    for item in a.binaries
    if not any(item[0].startswith(prefix) for prefix in _DROP_BINARIES)
]

pyz = PYZ(a.pure)


def build_exe(name: str, console: bool):
    return EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=console,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )


exe_cli = build_exe("vid2note-server", console=True)
