"""Vosk 模型查找与停顿分句，不联网。"""

import sys

from vidnote.asr import _group_words, _sentence_end, ensure_model


def _word(text: str, start: float, end: float) -> dict:
    return {"word": text, "start": start, "end": end}


def test_bundled_vosk_model_is_preferred(monkeypatch, tmp_path) -> None:
    folder = "vosk-model-small-cn-0.22"
    target = tmp_path / "vidnote" / "models" / folder
    target.mkdir(parents=True)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert ensure_model("vosk-cn") == target


def test_group_words_breaks_on_long_pause() -> None:
    cues = _group_words(
        [
            _word("今天", 0.0, 0.5),
            _word("我们", 0.6, 1.0),
            _word("开始", 2.0, 2.4),
        ]
    )
    assert [cue.text for cue in cues] == ["今天我们。", "开始。"]
    assert cues[1].start == 2.0


def test_group_words_adds_question_mark() -> None:
    cues = _group_words(
        [_word("大家", 0.0, 0.3), _word("好", 0.3, 0.5), _word("吗", 0.5, 0.7)]
    )
    assert cues[0].text == "大家好吗？"


def test_group_words_adds_comma_at_medium_pause() -> None:
    cues = _group_words(
        [
            _word("今天", 0.0, 0.3),
            _word("我们", 0.3, 0.6),
            _word("来", 0.6, 0.8),
            _word("聊聊", 0.8, 1.1),
            _word("这个", 1.1, 1.4),
            _word("话题", 1.4, 1.7),
            _word("吧", 1.7, 1.9),
            _word("然后", 2.3, 2.7),
        ]
    )
    assert len(cues) == 1
    assert "，" in cues[0].text
    assert cues[0].text.endswith("。")


def test_group_words_limits_sentence_length() -> None:
    words = [_word("测试", i * 0.2, i * 0.2 + 0.15) for i in range(40)]
    cues = _group_words(words)
    assert len(cues) > 1
    assert all(len(cue.text) <= 44 for cue in cues)


def test_sentence_end_detects_question_and_exclamation() -> None:
    assert _sentence_end("是不是真的") == "是不是真的？"
    assert _sentence_end("太好啊") == "太好啊！"
    assert _sentence_end("我们开始") == "我们开始。"
