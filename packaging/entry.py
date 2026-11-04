"""PyInstaller 的入口脚本。

会打包出两个 exe：

- ``vidnote.exe``    —— 命令行版（带控制台），支持 fetch / search / gui 等所有命令；
- ``vidnote-ui.exe`` —— 双击即开界面，不弹控制台窗口，忽略命令行参数。

注意：这里**延迟导入** ``vidnote.cli``。窗口版 exe 没有 stdout/stderr，而 cli
模块在导入时会创建 rich 的 Console 对象，早期导入会在启动阶段就崩掉。
"""

import sys
import tempfile
from pathlib import Path


def _trace(message: str) -> None:
    """启动阶段的诊断：窗口版没有控制台，只能写文件。"""
    try:
        path = Path(tempfile.gettempdir()) / "vidnote-ui.log"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[entry] {message}\n")
    except OSError:
        pass


def main() -> int:
    frozen = getattr(sys, "frozen", False)
    name = Path(sys.argv[0]).stem.lower()
    _trace(f"start frozen={frozen} name={name} argv={sys.argv[1:]}")

    gui_build = frozen and name.endswith("-ui")
    no_args = len(sys.argv) == 1
    _trace(f"gui_build={gui_build} no_args={no_args}")

    if gui_build or (frozen and no_args):
        from vidnote.gui import serve

        _trace("calling serve()")
        serve()
        return 0

    from vidnote.cli import app

    return app(prog_name="vidnote")


if __name__ == "__main__":
    sys.exit(main())
