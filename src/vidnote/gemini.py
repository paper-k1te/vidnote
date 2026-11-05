"""Gemini 云端转写（实验分支）。

把音频切成一分钟级的 WAV 片段，通过 Gemini 的 generateContent 接口上传，
要求它返回带时间戳的逐字转写。音频会离开本机，所以这个功能默认不启用，
API Key 只从参数或环境变量读取，不写进笔记、不落盘。
"""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import time
import wave
from pathlib import Path

import httpx

from .bilibili import Cue, VideoMeta
from .media import (
    MediaError,
    ProgressFn,
    StatusFn,
    download_audio,
    load_cached,
    save_cached,
)

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash"
SAMPLE_RATE = 16000
CHUNK_SECONDS = 240
_CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS

_PROMPT = """你是一个逐字转写器。请完整转写这段音频，不要总结、不要省略、不要改写。
按语义分成短句，每句给出相对于这段音频开头的 start 和 end 秒数（数字，保留两位小数）。
如果某处听不清，写 [听不清]，不要猜测。保留英文术语、数字和专有名词。
如果音频是中文，用中文写；如果是英文，保留英文。
只输出 JSON：{"segments": [{"start": 0.0, "end": 2.5, "text": "..."}]}"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "text": {"type": "string"},
                },
                "required": ["start", "end", "text"],
            },
        }
    },
    "required": ["segments"],
}


class GeminiError(RuntimeError):
    """缺少 Key、上传/转写失败或返回内容不可用。"""


def api_key(value: str | None = None) -> str:
    key = (
        (value or "")
        or os.environ.get("GEMINI_API_KEY", "")
        or os.environ.get("GOOGLE_API_KEY", "")
    ).strip()
    if not key:
        raise GeminiError(
            "缺少 Gemini API Key。在左侧「下载」页填写，或设置环境变量 GEMINI_API_KEY。"
        )
    return key


def _model_name(value: str | None) -> str:
    name = (value or "").strip() or DEFAULT_MODEL
    if name.startswith("models/"):
        name = name[len("models/") :]
    return name


def _cache_key(model: str) -> str:
    return "gemini-" + re.sub(r"[^A-Za-z0-9._-]", "_", model)


def _write_wav_chunks(
    audio: Path,
    workdir: Path,
    *,
    on_progress: ProgressFn | None = None,
) -> list[tuple[Path, float]]:
    """用 PyAV 解码成 16 kHz 单声道 WAV，并切成固定长度的小段。"""
    try:
        import av  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise GeminiError("缺少 av，无法解码音频；请使用完整版。") from exc

    try:
        container = av.open(str(audio))
    except Exception as exc:  # noqa: BLE001
        raise GeminiError(f"打不开音频：{exc}") from exc

    chunks: list[tuple[Path, float]] = []
    path: Path | None = None
    handle: wave.Wave_write | None = None
    frames_in_chunk = 0

    def open_chunk(index: int) -> tuple[Path, wave.Wave_write]:
        target = workdir / f"chunk-{index:04d}.wav"
        writer = wave.open(str(target), "wb")
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        return target, writer

    path, handle = open_chunk(0)
    try:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        total = float(stream.duration * stream.time_base) if stream.duration else 0.0

        def feed(data: bytes) -> None:
            nonlocal path, handle, frames_in_chunk
            offset = 0
            while offset < len(data):
                room = _CHUNK_SAMPLES - frames_in_chunk
                take = min(len(data) - offset, room * 2)
                assert handle is not None
                handle.writeframesraw(data[offset : offset + take])
                frames_in_chunk += take // 2
                offset += take
                if frames_in_chunk >= _CHUNK_SAMPLES:
                    handle.close()
                    chunks.append((path, CHUNK_SECONDS))
                    path, handle = open_chunk(len(chunks))
                    frames_in_chunk = 0

        for frame in container.decode(stream):
            for resampled in resampler.resample(frame):
                samples = int(resampled.samples)
                feed(bytes(resampled.planes[0])[: samples * 2])
            if on_progress and total and frame.time is not None:
                on_progress(float(frame.time), total)

        for resampled in resampler.resample(None):
            samples = int(resampled.samples)
            feed(bytes(resampled.planes[0])[: samples * 2])

        if frames_in_chunk:
            handle.close()
            chunks.append((path, frames_in_chunk / SAMPLE_RATE))
        else:
            handle.close()
            if path.exists() and path.stat().st_size <= 44:
                path.unlink(missing_ok=True)
    except GeminiError:
        raise
    except Exception as exc:  # noqa: BLE001 - PyAV 的错误类型很杂
        raise GeminiError(f"解码音频失败：{exc}") from exc
    finally:
        container.close()

    if not chunks:
        raise GeminiError("音频里没有可用的声音。")
    return chunks


def _timestamp_seconds(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    if ":" in text:
        parts = text.split(":")
        try:
            numbers = [float(part) for part in parts]
        except ValueError:
            return 0.0
        seconds = 0.0
        for number in numbers:
            seconds = seconds * 60 + number
        return seconds
    try:
        return float(text)
    except ValueError:
        return 0.0


def _extract_json(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _segments_to_cues(
    payload: dict,
    *,
    offset: float,
    duration: float,
) -> list[Cue]:
    raw = payload.get("segments")
    if not isinstance(raw, list):
        return []
    starts = []
    for item in raw:
        if not isinstance(item, dict):
            starts.append(0.0)
            continue
        starts.append(
            _timestamp_seconds(
                item.get("start", item.get("start_time", item.get("timestamp", 0)))
            )
        )
    cues: list[Cue] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        start = max(0.0, min(float(starts[index]), duration))
        explicit_end = item.get("end", item.get("end_time"))
        if explicit_end is None and index + 1 < len(starts):
            end = min(float(starts[index + 1]), duration)
        else:
            end = _timestamp_seconds(explicit_end) if explicit_end is not None else start + 2.0
        end = max(start + 0.1, min(float(end), duration))
        cues.append(Cue(start=offset + start, end=offset + end, text=text))
    cues.sort(key=lambda cue: cue.start)
    return cues


def _post_chunk(
    body: dict,
    *,
    key: str,
    model: str,
    client: httpx.Client | None = None,
    retry_delay: float = 1.0,
) -> dict:
    url = f"{API_BASE}/models/{model}:generateContent"
    owned = client is None
    active = client or httpx.Client(timeout=httpx.Timeout(600.0, connect=20.0))
    try:
        for attempt in range(3):
            response = active.post(
                url,
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json=body,
            )
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                delay = retry_delay * (2**attempt)
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        pass
                time.sleep(min(delay, 10.0))
                continue
            try:
                data = response.json()
            except ValueError as exc:
                raise GeminiError(
                    f"Gemini 返回了无法解析的内容（HTTP {response.status_code}）"
                ) from exc
            if response.status_code >= 400:
                error = data.get("error") if isinstance(data, dict) else None
                message = (
                    error.get("message")
                    if isinstance(error, dict)
                    else str(error or response.text[:200])
                )
                raise GeminiError(f"Gemini API 错误（HTTP {response.status_code}）：{message}")
            return data
        raise GeminiError("Gemini API 连续失败，请稍后重试。")
    finally:
        if owned:
            active.close()


def _text_from_response(data: dict) -> str:
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise GeminiError(f"Gemini 拒绝对这段音频生成内容：{feedback['blockReason']}")
    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiError("Gemini 没有返回转写结果。")
    candidate = candidates[0]
    finish = candidate.get("finishReason")
    if finish in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"}:
        raise GeminiError(f"Gemini 因内容限制停止转写：{finish}")
    content = candidate.get("content") or {}
    parts = content.get("parts") or []
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    if not text:
        raise GeminiError("Gemini 返回了空转写。")
    return text


def _transcribe_chunk(
    path: Path,
    *,
    offset: float,
    duration: float,
    key: str,
    model: str,
    client: httpx.Client | None = None,
    on_status: StatusFn | None = None,
) -> list[Cue]:
    raw = path.read_bytes()
    body = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "你是专业的逐字转写器。只转写音频里实际说出的内容，"
                        "不总结、不补充、不编造；听不清就写 [听不清]。"
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": _PROMPT},
                    {
                        "inlineData": {
                            "mimeType": "audio/wav",
                            "data": base64.b64encode(raw).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": _SCHEMA,
        },
    }
    data = _post_chunk(body, key=key, model=model, client=client)
    text = _text_from_response(data)
    payload = _extract_json(text)
    if payload is None:
        if on_status:
            on_status("Gemini 返回了纯文本，按整段估算时间戳…")
        cleaned = text.strip()
        return [Cue(start=offset, end=offset + duration, text=cleaned)] if cleaned else []
    return _segments_to_cues(payload, offset=offset, duration=duration)


def transcribe_audio(
    audio: Path,
    *,
    api_key_value: str | None = None,
    model: str = DEFAULT_MODEL,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    """把本地音频交给 Gemini，返回 (语言, 带全局时间戳的 Cue)。"""
    key = api_key(api_key_value)
    selected = _model_name(model)
    with tempfile.TemporaryDirectory(prefix="vidnote-gemini-") as tmp:
        chunks = _write_wav_chunks(audio, Path(tmp), on_progress=on_progress)
        total = sum(duration for _, duration in chunks)
        cues: list[Cue] = []
        start = 0.0
        for index, (path, duration) in enumerate(chunks):
            if on_status:
                on_status(f"正在上传第 {index + 1}/{len(chunks)} 段音频到 Gemini…")
            cues.extend(
                _transcribe_chunk(
                    path,
                    offset=start,
                    duration=duration,
                    key=key,
                    model=selected,
                    on_status=on_status,
                )
            )
            start += duration
            if on_progress and total:
                on_progress(min(start, total), total)
    if not cues:
        raise GeminiError("Gemini 没有识别出文字，可能是纯音乐或人声太轻。")
    return "zh", cues


def transcribe_video(
    meta: VideoMeta,
    page: int,
    *,
    api_key_value: str | None = None,
    model: str = DEFAULT_MODEL,
    use_cache: bool = True,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    """下载音频 → Gemini 云端转写 → 写缓存。"""
    selected = _model_name(model)
    cache_key = _cache_key(selected)
    if use_cache and (cached := load_cached(meta.bvid, page, cache_key)):
        if on_status:
            on_status("正在读取 Gemini 转写缓存…")
        return cached

    key = api_key(api_key_value)
    url = f"{meta.url}?p={page}" if len(meta.pages) > 1 else meta.url
    with tempfile.TemporaryDirectory(prefix="vidnote-gemini-audio-") as tmp:
        try:
            audio = download_audio(
                url, Path(tmp), on_progress=on_progress, on_status=on_status
            )
        except MediaError as exc:
            raise GeminiError(str(exc)) from exc
        language, cues = transcribe_audio(
            audio,
            api_key_value=key,
            model=selected,
            on_progress=on_progress,
            on_status=on_status,
        )

    if use_cache:
        save_cached(meta.bvid, page, cache_key, language, cues)
    return language, cues
