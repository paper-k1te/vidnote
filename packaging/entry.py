"""PyInstaller 的入口脚本。

单独放一个文件，避免把 ``if __name__ == "__main__"`` 的判断塞进包内部。
"""

import sys

from vidnote.cli import app

if __name__ == "__main__":
    sys.exit(app(prog_name="vidnote"))
