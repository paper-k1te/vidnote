"""云端语音转写（Gemini / OpenAI 兼容 Whisper）。

为什么有它：本地 Vosk 模型 42 MB、whisper 最小 145 MB，都要随包分发或下载。
默认改成联网转写后，安装包不再带模型，第一次用只需一个 API Key。

两个提供方：
- ``gemini``：Gemini 2.5 Flash 直接听音频，按 4 分钟切片，返回带时间戳的
  逐句转写。音频会上传到 Google。
- ``whisper``：任何兼容 OpenAI ``/audio/transcriptions`` 的服务（OpenAI、
  硅基流动、Groq、国内厂商），走 ``verbose_json`` 拿逐句时间戳。

Key 只从参数或环境变量读取，不写进笔记、不落盘。环境变量优先级：
``VID2NOTE_ASR_KEY`` > 提供方自己的 ``GEMINI_API_KEY`` / ``OPENAI_API_KEY``。
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
from .media import ProgressFn, StatusFn, download_audio, load_cached, save_cached
from .net import system_proxy

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_WHISPER_BASE = "https://api.openai.com/v1"
DEFAULT_WHISPER_MODEL = "whisper-1"
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


class CloudAsrError(RuntimeError):
    """缺 Key、上传/转写失败或返回内容不可用。"""


def _env_key(provider: str) -> str:
    names = ["VID2NOTE_ASR_KEY"]
    if provider == "gemini":
        names += ["GEMINI_API_KEY", "GOOGLE_API_KEY"]
    else:
        names += ["OPENAI_API_KEY"]
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def resolve_provider(requested: str | None, *, api_key: str | None = None) -> str:
    """决定用哪个提供方：显式指定优先，auto 时看环境里配了谁的 Key。"""
    value = (requested or os.environ.get("VID2NOTE_ASR_PROVIDER") or "auto").strip().lower()
    if value in ("gemini", "google"):
        return "gemini"
    if value in ("whisper", "openai", "whisper-api"):
        return "whisper"
    if api_key:
        return "whisper" if not (api_key.startswith("AIza") or api_key.startswith("AQ.")) else "gemini"
    if _env_key("gemini"):
        return "gemini"
    if _env_key("whisper"):
        return "whisper"
    raise CloudAsrError(
        "云端转写需要 API Key：在设置里填写 Gemini 或 OpenAI 兼容的 Key，"
        "或设置环境变量 GEMINI_API_KEY / OPENAI_API_KEY。"
    )


def _model_for(provider: str, value: str | None) -> str:
    name = (value or "").strip()
    if provider == "gemini":
        if not name or name in ("cloud", "gemini", "whisper", "whisper-api"):
            name = DEFAULT_GEMINI_MODEL
        return name.removeprefix("models/")
    if not name or name in ("cloud", "gemini", "whisper", "whisper-api"):
        return DEFAULT_WHISPER_MODEL
    return name


def _key_for(provider: str, value: str | None) -> str:
    key = (value or "").strip() or _env_key(provider)
    if not key:
        raise CloudAsrError(
            "缺少转写 API Key。在设置里填写，或设置 GEMINI_API_KEY / OPENAI_API_KEY。"
        )
    return key


def _cache_name(provider: str, model: str) -> str:
    return "cloud-" + provider + "-" + re.sub(r"[^A-Za-z0-9._-]", "_", model)


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
        raise CloudAsrError("缺少 av，无法解码音频。") from exc

    try:
        container = av.open(str(audio))
    except Exception as exc:  # noqa: BLE001
        raise CloudAsrError(f"打不开音频：{exc}") from exc

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
    except CloudAsrError:
        raise
    except Exception as exc:  # noqa: BLE001 - PyAV 的错误类型很杂
        raise CloudAsrError(f"解码音频失败：{exc}") from exc
    finally:
        container.close()

    if not chunks:
        raise CloudAsrError("音频里没有可用的声音。")
    return chunks


def _timestamp_seconds(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    if ":" in text:
        try:
            numbers = [float(part) for part in text.split(":")]
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


def _segments_to_cues(payload: dict, *, offset: float, duration: float) -> list[Cue]:
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


def _post_gemini(body: dict, *, key: str, model: str, retry_delay: float = 1.0) -> dict:
    url = f"{GEMINI_BASE}/models/{model}:generateContent"
    with httpx.Client(timeout=httpx.Timeout(600.0, connect=20.0), proxy=system_proxy()) as client:
        for attempt in range(3):
            try:
                response = client.post(
                    url,
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json=body,
                )
            except httpx.HTTPError as exc:
                raise CloudAsrError(f"连不上 Gemini（{exc}）。如果在中国大陆，请先开启代理。") from exc
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
                raise CloudAsrError(f"Gemini 返回了无法解析的内容（HTTP {response.status_code}）") from exc
            if response.status_code >= 400:
                error = data.get("error") if isinstance(data, dict) else None
                message = error.get("message") if isinstance(error, dict) else str(error or response.text[:200])
                raise CloudAsrError(f"Gemini API 错误（HTTP {response.status_code}）：{message}")
            return data
    raise CloudAsrError("Gemini API 连续失败，请稍后重试。")


def _gemini_text(data: dict) -> str:
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise CloudAsrError(f"Gemini 拒绝对这段音频生成内容：{feedback['blockReason']}")
    candidates = data.get("candidates") or []
    if not candidates:
        raise CloudAsrError("Gemini 没有返回转写结果。")
    candidate = candidates[0]
    finish = candidate.get("finishReason")
    if finish in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"}:
        raise CloudAsrError(f"Gemini 因内容限制停止转写：{finish}")
    content = candidate.get("content") or {}
    parts = content.get("parts") or []
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    if not text:
        raise CloudAsrError("Gemini 返回了空转写。")
    return text


def _gemini_chunk(
    path: Path,
    *,
    offset: float,
    duration: float,
    key: str,
    model: str,
    on_status: StatusFn | None = None,
) -> list[Cue]:
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
                            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
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
    text = _gemini_text(_post_gemini(body, key=key, model=model))
    payload = _extract_json(text)
    if payload is None:
        if on_status:
            on_status("Gemini 返回了纯文本，按整段估算时间戳…")
        cleaned = text.strip()
        return [Cue(start=offset, end=offset + duration, text=cleaned)] if cleaned else []
    return _segments_to_cues(payload, offset=offset, duration=duration)


def _transcribe_gemini(
    audio: Path,
    *,
    key: str,
    model: str,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    with tempfile.TemporaryDirectory(prefix="vid2note-gemini-") as tmp:
        chunks = _write_wav_chunks(audio, Path(tmp), on_progress=on_progress)
        total = sum(duration for _, duration in chunks)
        cues: list[Cue] = []
        start = 0.0
        for index, (path, duration) in enumerate(chunks):
            if on_status:
                on_status(f"正在上传第 {index + 1}/{len(chunks)} 段音频到 Gemini…")
            cues.extend(
                _gemini_chunk(
                    path, offset=start, duration=duration, key=key, model=model, on_status=on_status
                )
            )
            start += duration
            if on_progress and total:
                on_progress(min(start, total), total)
    if not cues:
        raise CloudAsrError("Gemini 没有识别出文字，可能是纯音乐或人声太轻。")
    return "zh", cues


def _transcribe_whisper(
    audio: Path,
    *,
    key: str,
    base_url: str,
    model: str,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    base = (base_url or DEFAULT_WHISPER_BASE).rstrip("/")
    if on_status:
        on_status("正在上传音频到转写接口…")
    try:
        with audio.open("rb") as handle:
            response = httpx.post(
                f"{base}/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": (audio.name, handle, "application/octet-stream")},
                data={"model": model, "response_format": "verbose_json"},
                timeout=httpx.Timeout(600.0, connect=20.0),
                proxy=system_proxy(),
            )
    except httpx.HTTPError as exc:
        raise CloudAsrError(f"连不上转写接口（{exc}）。") from exc
    if response.status_code >= 400:
        try:
            message = response.json().get("error", {}).get("message")
        except ValueError:
            message = response.text[:200]
        raise CloudAsrError(f"转写接口错误（HTTP {response.status_code}）：{message}")
    try:
        data = response.json()
    except ValueError as exc:
        raise CloudAsrError("转写接口返回了无法解析的内容。") from exc
    if not isinstance(data, dict):
        raise CloudAsrError("转写接口返回格式不对。")
    raw = data.get("segments")
    if isinstance(raw, list) and raw:
        cues = _segments_to_cues(
            {"segments": [
                {
                    "start": item.get("start", 0),
                    "end": item.get("end", 0),
                    "text": item.get("text", ""),
                }
                for item in raw
                if isinstance(item, dict)
            ]},
            offset=0.0,
            duration=float(data.get("duration") or 0.0) or 1e9,
        )
    else:
        text = str(data.get("text") or "").strip()
        cues = [Cue(start=0.0, end=float(data.get("duration") or 0.0) or 1.0, text=text)] if text else []
    if not cues:
        raise CloudAsrError("转写接口没有返回文字。")
    return str(data.get("language") or "zh"), cues


def transcribe_audio(
    audio: Path,
    *,
    provider: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    """转写一个本地音频文件，返回 (语言, 带时间戳的 Cue)。"""
    selected = _model_for(provider, model or os.environ.get("VID2NOTE_ASR_MODEL"))
    key = _key_for(provider, api_key)
    base = base_url or os.environ.get("VID2NOTE_ASR_BASE") or ""
    if provider == "gemini":
        return _transcribe_gemini(audio, key=key, model=selected, on_progress=on_progress, on_status=on_status)
    return _transcribe_whisper(audio, key=key, base_url=base, model=selected, on_status=on_status)


def transcribe_video(
    meta: VideoMeta,
    page: int,
    *,
    provider: str = "auto",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    use_cache: bool = True,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> tuple[str, list[Cue]]:
    """下载音频 → 云端转写 → 写缓存。"""
    chosen = resolve_provider(provider, api_key=api_key)
    selected = _model_for(chosen, model)
    cache_key = _cache_name(chosen, selected)
    if use_cache and (cached := load_cached(meta.bvid, page, cache_key)):
        if on_status:
            on_status("正在读取转写缓存…")
        return cached

    url = f"{meta.url}?p={page}" if len(meta.pages) > 1 else meta.url
    with tempfile.TemporaryDirectory(prefix="vid2note-cloud-") as tmp:
        audio = download_audio(url, Path(tmp), on_progress=on_progress, on_status=on_status)
        language, cues = transcribe_audio(
            audio,
            provider=chosen,
            api_key=api_key,
            base_url=base_url,
            model=selected,
            on_progress=on_progress,
            on_status=on_status,
        )
    if use_cache:
        save_cached(meta.bvid, page, cache_key, language, cues)
    return language, cues
