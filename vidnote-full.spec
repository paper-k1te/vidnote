# -*- mode: python ; coding: utf-8 -*-
"""完整版打包配置：核心功能 + 本地转写（Vosk + whisper + yt-dlp）。

Vosk 是小引擎（运行库 13 MB、中文模型 42 MB），随后端一起分发；
faster-whisper 及 ctranslate2 / onnxruntime 也一并打包，所以完整版能直接选
whisper 模型。模型文件本身不放进安装包，第一次使用才下载到缓存目录，
下载进度会显示在界面和命令行里。

用法：
    pyinstaller vidnote-full.spec --noconfirm --distpath dist-exe-full --workpath build-exe-full
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

a = Analysis(
    ["packaging/entry.py"],
    pathex=["src"],
    # vosk 用 ctypes 加载自带的 libvosk.dll；ctranslate2 / onnxruntime 同理，
    # 它们原生库不会被自动收集。
    binaries=collect_dynamic_libs("vosk")
    + collect_dynamic_libs("ctranslate2")
    + collect_dynamic_libs("onnxruntime"),
    datas=[("src/vidnote/ui/index.html", "vidnote/ui")]
    + collect_data_files("vosk")
    + collect_data_files("srt")
    + collect_data_files("faster_whisper")
    + collect_data_files("huggingface_hub"),
    hiddenimports=[
        "vosk",
        "srt",
        "requests",
        "websockets",
        "av",
        "yt_dlp",
        "faster_whisper",
        "ctranslate2",
        "huggingface_hub",
        "tokenizers",
        "onnxruntime",
        "tqdm",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
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
