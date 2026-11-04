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
    datas=[("src/vidnote/ui/index.html", "vidnote/ui")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 可选功能的重型依赖（转写、按画面变化选帧）
        "faster_whisper",
        "ctranslate2",
        "onnxruntime",
        "tokenizers",
        "huggingface_hub",
        "vosk",
        "srt",
        "av",
        "yt_dlp",
        "numpy",
        # 与运行无关的东西
        "mcp",
        "tkinter",
        "pytest",
        "setuptools",
        # 桌面窗口由 C# 外壳（WebView2）负责，Python 侧不需要这些
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

# PIL 的预编译扩展是按二进制收集的，光靠 excludes 拦不住。这里显式丢掉用不到的：
# _avif 一个就占 4.3 MB（压缩后），_imagingft / _webp / _imagingcms 也用不上。
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


# 命令行版：有控制台，能看输出、能跑 fetch/search。
exe_cli = build_exe("vidnote", console=True)
# 界面版：双击即开，不弹命令行窗口。
exe_gui = build_exe("vidnote-ui", console=False)
