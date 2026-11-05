"""Vosk 本地转写（小引擎）。

为什么加它：faster-whisper 的模型最小也要 145 MB、常用 485 MB，太重。
Vosk 的中文小模型只有 42 MB，适合「只想有个大概文稿」的场景。

代价要说清楚：Vosk 原始输出不带标点。这里利用它给的逐词时间戳，按停顿
分句，并按常见的疑问/感叹句式补上 ``。？！``，读起来不会是一整块。

模型不在包里，第一次用的时候下载到 ``~/.cache/vidnote/vosk``。
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import httpx

from .bilibili import Cue
from .media import ProgressFn, StatusFn, cache_dir


class AsrError(RuntimeError):
    """下载、解码或识别失败。"""


# 目前只支持这一个模型：中文、42 MB、够小。
MODELS = {
    "vosk-cn": (
        "vosk-model-small-cn-0.22",
        "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip",
    )
}


def _model_dir(name: str) -> Path:
    return cache_dir() / "vosk" / name


def _bundled_model_dir(name: str) -> Path | None:
    """完整版 exe 把模型一起打包，直接从解压目录读取，不再下载。"""
    if not getattr(sys, "frozen", False):
        return None
    root = Path(getattr(sys, "_MEIPASS", "")) / "vidnote" / "models" / name
    return root if root.is_dir() else None


def ensure_model(key: str = "vosk-cn", on_progress: ProgressFn | None = None) -> Path:
    """确保模型已可用，返回模型目录。"""
    if key not in MODELS:
        raise AsrError(f"未知的 Vosk 模型：{key}")
    folder, url = MODELS[key]
    if bundled := _bundled_model_dir(folder):
        return bundled
    target = _model_dir(folder)
    if target.exists() and any(target.iterdir()):
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    archive = target.parent / f"{folder}.zip"

    try:
        with httpx.stream("GET", url, timeout=60.0, follow_redirects=True) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with archive.open("wb") as handle:
                for chunk in response.iter_bytes(1024 * 256):
                    handle.write(chunk)
                    done += len(chunk)
                    if on_progress and total:
                        on_progress(float(done), float(total))
    except Exception as exc:  # noqa: BLE001
        raise AsrError(f"下载 Vosk 模型失败：{exc}") from exc

    try:
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(target.parent)
    except Exception as exc:  # noqa: BLE001
        raise AsrError(f"解压模型失败：{exc}") from exc
    finally:
        archive.unlink(missing_ok=True)

    if not target.exists():
        raise AsrError(f"模型解压后找不到目录：{target}")
    return target


_SENTENCE_GAP = 0.75
_COMMA_GAP = 0.35
_MAX_CHARS = 42

_QUESTION_TAILS = ("吗", "呢", "么", "嘛")
_QUESTION_WORDS = (
    "为什么",
    "怎么",
    "怎样",
    "什么",
    "哪",
    "谁",
    "多少",
    "是不是",
    "有没有",
    "对不对",
    "好不好",
    "行不行",
    "可不可以",
    "能不能",
    "要不要",
)
_EXCLAIM_TAILS = ("啊", "呀", "哇")


def _append(text: str, token: str) -> str:
    if not text:
        return token
    if (
        text[-1].isascii()
        and text[-1].isalnum()
        and token[:1].isascii()
        and token[:1].isalnum()
    ):
        return f"{text} {token}"
    return text + token


def _sentence_end(text: str) -> str:
    """按句尾判断用问号、感叹号还是句号。"""
    core = text.rstrip("，、；： ")
    if core.endswith(("。", "？", "！", "?", "!", ".")):
        return core
    if core.endswith(_QUESTION_TAILS) or core.endswith(_QUESTION_WORDS):
        return core + "？"
    if any(word in core[-12:] for word in _QUESTION_WORDS[7:]):
        return core + "？"
    if core.endswith(_EXCLAIM_TAILS):
        return core + "！"
    return core + "。"


def _group_words(
    words: list[dict],
    *,
    max_gap: float = _SENTENCE_GAP,
    comma_gap: float = _COMMA_GAP,
    max_chars: int = _MAX_CHARS,
) -> list[Cue]:
    """把逐词结果拼成句子：长停顿断句，中等停顿补逗号，句尾补标点。"""
    cues: list[Cue] = []
    buffer: list[dict] = []
    text = ""

    def flush() -> None:
        nonlocal text
        body = text.rstrip("，、；： ")
        if body:
            start = float(buffer[0].get("start", 0.0))
            end = float(buffer[-1].get("end", start))
            cues.append(Cue(start=start, end=end, text=_sentence_end(text)))
        buffer.clear()
        text = ""

    for word in words:
        token = str(word.get("word", "")).strip()
        if not token:
            continue
        if buffer:
            gap = float(word.get("start", 0.0)) - float(buffer[-1].get("end", 0.0))
            if gap >= max_gap:
                flush()
            elif (
                gap >= comma_gap
                and len(text) >= 12
                and not text.endswith(("，", "。", "？", "！"))
            ):
                text += "，"
        buffer.append(word)
        text = _append(text, token)
        if len(text.replace("，", "")) >= max_chars:
            flush()
    flush()
    return cues


def transcribe(
    audio: Path,
    *,
    model: str = "vosk-cn",
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    """用 Vosk 转写本地音频文件。"""
    try:
        import av  # noqa: PLC0415
        import vosk  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise AsrError("缺少 vosk 或 av，请先安装：pip install 'vidnote[vosk]'") from exc

    vosk.SetLogLevel(-1)
    if on_status:
        on_status("正在准备 Vosk 模型…")
    directory = ensure_model(model, on_progress=on_progress)
    if on_status:
        on_status("正在本地转写…")
    recognizer = vosk.KaldiRecognizer(vosk.Model(str(directory)), 16000)
    recognizer.SetWords(True)

    cues: list[Cue] = []
    try:
        container = av.open(str(audio))
    except Exception as exc:  # noqa: BLE001
        raise AsrError(f"打不开音频：{exc}") from exc

    try:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        total = float(stream.duration * stream.time_base) if stream.duration else 0.0

        for frame in container.decode(stream):
            for resampled in resampler.resample(frame):
                data = bytes(resampled.planes[0])[: resampled.samples * 2]
                if recognizer.AcceptWaveform(data):
                    cues.extend(_group_words(json.loads(recognizer.Result()).get("result", [])))
            if on_progress and total and frame.time is not None:
                on_progress(float(frame.time), total)

        for resampled in resampler.resample(None):
            data = bytes(resampled.planes[0])[: resampled.samples * 2]
            if recognizer.AcceptWaveform(data):
                cues.extend(_group_words(json.loads(recognizer.Result()).get("result", [])))
        cues.extend(_group_words(json.loads(recognizer.FinalResult()).get("result", [])))
    finally:
        container.close()

    if not cues:
        raise AsrError("没有识别出文字，可能是纯音乐或人声太轻。")
    return "zh", cues


def transcribe_video(
    meta,
    page: int,
    *,
    model: str = "vosk-cn",
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    """下载音频 → Vosk 转写，一步到位。"""
    import tempfile  # noqa: PLC0415

    from .media import download_audio  # noqa: PLC0415

    url = f"{meta.url}?p={page}" if len(meta.pages) > 1 else meta.url
    with tempfile.TemporaryDirectory(prefix="vidnote-asr-") as tmp:
        audio = download_audio(
            url, Path(tmp), on_progress=on_progress, on_status=on_status
        )
        return transcribe(
            audio, model=model, on_progress=on_progress, on_status=on_status
        )
