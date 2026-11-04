# -*- mode: python ; coding: utf-8 -*-
"""完整版打包配置：核心功能 + 本地转写（faster-whisper / yt-dlp）。

体积会到 300 MB 以上，因为 ctranslate2、onnxruntime、PyAV 都带原生库。
第一次转写时仍会从 HuggingFace 下载模型（small 约 485 MB），这一步无法预打包进 exe。

用法：
    pyinstaller vidnote-full.spec --noconfirm --distpath dist-exe-full --workpath build-exe-full
"""

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ["packaging/entry.py"],
    pathex=["src"],
    binaries=[],
    # faster-whisper 自带 VAD 模型（silero_vad_v6.onnx），不显式收集会报 NO_SUCHFILE。
    datas=[("src/vidnote/ui/index.html", "vidnote/ui")]
    + collect_data_files("faster_whisper"),
    hiddenimports=[
        "faster_whisper",
        "ctranslate2",
        "onnxruntime",
        "tokenizers",
        "huggingface_hub",
        "av",
        "yt_dlp",
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
