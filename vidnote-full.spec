# -*- mode: python ; coding: utf-8 -*-
"""完整版打包配置：核心功能 + 本地转写（Vosk 小引擎 + yt-dlp）。

为什么用 Vosk 而不是 faster-whisper：whisper 的模型最小 145 MB、常用 485 MB，
加上 ctranslate2 / onnxruntime 会让包到 100 MB 以上。Vosk 运行库 13 MB、中文模型
42 MB，整包能控制在 50 MB 左右，模型第一次用时才下载。

想要更好的中文质量，仍可以用 pip 安装的 whisper 版本。

用法：
    pyinstaller vidnote-full.spec --noconfirm --distpath dist-exe-full --workpath build-exe-full
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

a = Analysis(
    ["packaging/entry.py"],
    pathex=["src"],
    # vosk 用 ctypes 加载自带的 libvosk.dll，默认不会被收集。
    binaries=collect_dynamic_libs("vosk"),
    datas=[("src/vidnote/ui/index.html", "vidnote/ui")]
    + collect_data_files("vosk")
    + collect_data_files("srt"),
    hiddenimports=["vosk", "srt", "requests", "websockets", "av", "yt_dlp"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 不打包 whisper 那一套（用户要的话走 pip 安装）
        "faster_whisper",
        "ctranslate2",
        "onnxruntime",
        "tokenizers",
        "huggingface_hub",
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
        "PIL.ImageFont",
        "PIL.ImageDraw",
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


exe_cli = build_exe("vidnote-server", console=True)
