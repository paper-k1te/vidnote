# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

只打「核心版」：抓取、搜索、笔记、MCP。转写（faster-whisper / ctranslate2）和
抽帧（PyAV / Pillow）依赖重型原生库，会把体积推到几百 MB，所以排除在外——
需要它们时仍然用 pip 安装的完整版。

用法：
    pyinstaller vidnote.spec --noconfirm --distpath dist-exe --workpath build-exe
"""

a = Analysis(
    ["packaging/entry.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 可选功能的重型依赖
        "faster_whisper",
        "ctranslate2",
        "onnxruntime",
        "tokenizers",
        "huggingface_hub",
        "av",
        "PIL",
        "yt_dlp",
        "numpy",
        # 与运行无关的东西
        "mcp",
        "tkinter",
        "pytest",
        "setuptools",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="vidnote",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
