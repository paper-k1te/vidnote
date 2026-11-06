# -*- mode: python ; coding: utf-8 -*-
"""桌面版打包配置：核心功能 + Vosk 本地转写 + yt-dlp。

Vosk 引擎和中文模型（约 65 MB）直接打进 exe，第一次转写不用再下载；
whisper 的推理引擎（ctranslate2 / onnxruntime / tokenizers 等）默认不打进
exe，第一次要用 whisper 时由界面单独下载。

用法：
    pyinstaller vid2note-app.spec --noconfirm --distpath dist-exe --workpath build-exe
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

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
    binaries=collect_dynamic_libs("vosk"),
    datas=[
        ("src/vid2note/ui/index.html", "vid2note/ui"),
        ("src/vidnote/ui/index.html", "vidnote/ui"),
        (_MODEL_DIR, f"vid2note/models/{_MODEL_FOLDER}"),
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
        "tqdm.auto",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "ctranslate2",
        "faster_whisper",
        "onnxruntime",
        "tokenizers",
        "transformers",
        "torch",
        "numpy.testing",
        "matplotlib",
        "scipy",
        "pandas",
        "setuptools",
        "distutils",
        "unittest",
        "pytest",
        "xmlrpc",
        "pydoc",
        "tkinter",
        "curses",
        "sqlite3",
        "_sqlite3",
        "cryptography",
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


exe_cli = build_exe("vid2note-server", console=True)
