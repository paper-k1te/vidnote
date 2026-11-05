# -*- mode: python ; coding: utf-8 -*-
"""完整版打包配置：核心功能 + Vosk 本地转写 + yt-dlp。

Vosk 小引擎和中文模型（约 65 MB）直接打进 exe，第一次转写不用再下载；
whisper 的推理引擎（ctranslate2 / onnxruntime / tokenizers 等）默认不打进
exe，第一次要用 whisper 时由界面单独下载 ``vidnote-whisper-deps-<版本>.zip``。

用法：
    pyinstaller vidnote-full.spec --noconfirm --distpath dist-exe-full --workpath build-exe-full
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Vosk 小模型直接打进 exe，第一次转写不用再下载。
_MODEL_FOLDER = "vosk-model-small-cn-0.22"
_MODEL_DIR = os.path.join("assets", _MODEL_FOLDER)
if not os.path.isdir(_MODEL_DIR):
    raise SystemExit(
        f"找不到 Vosk 模型：{_MODEL_DIR}\n"
        "先运行 scripts/build_app.ps1 -Full，脚本会自动复制或下载模型。"
    )

a = Analysis(
    ["packaging/entry.py"],
    pathex=["src"],
    # vosk 用 ctypes 加载自带的 libvosk.dll；原生库不会被自动收集。
    binaries=collect_dynamic_libs("vosk"),
    datas=[
        ("src/vidnote/ui/index.html", "vidnote/ui"),
        (_MODEL_DIR, f"vidnote/models/{_MODEL_FOLDER}"),
    ]
    + collect_data_files("vosk")
    + collect_data_files("srt"),
    hiddenimports=[
        "vosk",
        "srt",
        "requests",
        "av",
        "yt_dlp",
        "vidnote.gemini",
        "vidnote.llm",
        # vosk 在导入时就会 import tqdm；whisper 用 tqdm.auto。
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
