"""PyInstaller 的入口脚本。

产物：

- ``vid2note.exe``        —— 命令行版（带控制台），支持 fetch / search / gui 等所有命令；
- ``vid2note-server.exe`` —— 同一个程序，供桌面外壳调用
  （``serve-ui`` 模式：只起后端，不开浏览器）。
"""

import sys
import tempfile
from pathlib import Path


def _trace(message: str) -> None:
    try:
        path = Path(tempfile.gettempdir()) / "vid2note-ui.log"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[entry] {message}\n")
    except OSError:
        pass


def main() -> int:
    frozen = getattr(sys, "frozen", False)
    name = Path(sys.argv[0]).stem.lower()
    _trace(f"start frozen={frozen} name={name} argv={sys.argv[1:]}")

    if frozen and name.endswith("-ui"):
        try:
            from vid2note.gui import serve
        except ImportError:
            from vidnote.gui import serve

        _trace("legacy ui build -> browser mode")
        serve()
        return 0

    try:
        from vid2note.cli import app
    except ImportError:
        from vidnote.cli import app

    prog = "vid2note" if "vid2note" in name else "vidnote"
    return app(prog_name=prog)


if __name__ == "__main__":
    sys.exit(main())
