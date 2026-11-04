"""PyInstaller 的入口脚本。

产物：

- ``vidnote.exe``    —— 命令行版（带控制台），支持 fetch / search / gui 等所有命令；
- ``vidnote-server.exe`` —— 同一个程序，供桌面外壳 ``vidnote-app.exe`` 调用
  （``serve-ui`` 模式：只起后端，不开浏览器）。

注意：这里**延迟导入** ``vidnote.cli``。窗口版 exe 没有 stdout/stderr，而 cli
模块在导入时会创建 rich 的 Console 对象，早期导入会在启动阶段就崩掉。
"""

import sys
import tempfile
from pathlib import Path


def _trace(message: str) -> None:
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

    if frozen and name.endswith("-ui"):
        from vidnote.gui import serve

        _trace("legacy ui build -> browser mode")
        serve()
        return 0

    from vidnote.cli import app

    return app(prog_name="vidnote")


if __name__ == "__main__":
    sys.exit(main())
