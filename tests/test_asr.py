"""打包后的 Vosk 模型查找逻辑，不联网。"""

import sys

from vidnote.asr import ensure_model


def test_bundled_vosk_model_is_preferred(monkeypatch, tmp_path) -> None:
    folder = "vosk-model-small-cn-0.22"
    target = tmp_path / "vidnote" / "models" / folder
    target.mkdir(parents=True)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert ensure_model("vosk-cn") == target
