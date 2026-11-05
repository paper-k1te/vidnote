"""用任意 OpenAI 兼容的 LLM 精修粗转写，并生成摘要和要点。

分工：Vosk 负责「听」——本地、免费、有逐句时间戳；LLM 负责「读」——
修正同音字、补标点、挑出关键点。这样不需要云端语音模型，也不用上传音频。

转写文本会发到 LLM 服务商，所以默认关闭；Key 只从参数或环境变量读取，
不写进笔记、不落盘。接口按 OpenAI 的 ``/chat/completions`` 约定，DeepSeek、
通义千问、智谱、Kimi、OpenAI 都能直接用。
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

import httpx

from .bilibili import Cue, VideoMeta
from .media import ProgressFn, StatusFn
from .net import system_proxy

DEFAULT_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

_CHUNK_CUES = 120
_CHUNK_CHARS = 6000

_SYSTEM = """你是中文视频笔记编辑。用户会给你一段语音识别的粗转写，里面可能有\
同音字、错别字、缺失的标点。请在保留原意的前提下修正文字，并挑出这一段的关键点。
规则：
1. segments 必须逐条对应输入编号，不合并、不拆分、不遗漏，只改文字，不改编号。
2. 补全标点，修正明显的同音字、错别字和专有名词；听不清的保留原文，绝不编造。
3. 可以去掉「嗯、啊」这类纯语气词，但不要删掉任何事实信息。
4. points 选 1-3 条，i 用这一段里的编号，title 不超过 12 字，detail 不超过 40 字。
只输出 JSON：
{"segments":[{"i":0,"text":"..."}],"points":[{"i":3,"title":"...","detail":"..."}]}"""

_SUMMARY_SYSTEM = """你是中文视频笔记编辑。根据给出的要点，写一段 120 字以内的摘要，\
概括主题、结构和结论，不要罗列，不要编造。只输出摘要正文。"""

_SCHEMA_HINT = """示例：
{"segments":[{"i":0,"text":"今天我们来聊一聊..."}],\
"points":[{"i":2,"title":"核心结论","detail":"..."}]}"""


class LlmError(RuntimeError):
    """缺少 Key、接口地址错误或调用失败。"""


@dataclass(frozen=True)
class KeyPoint:
    seconds: float
    title: str
    detail: str


@dataclass
class Refined:
    cues: list[Cue]
    summary: str = ""
    points: list[KeyPoint] = field(default_factory=list)
    model: str = ""
    changed: bool = False
    errors: list[str] = field(default_factory=list)


def api_key(value: str | None = None) -> str:
    key = (
        (value or "")
        or os.environ.get("VIDNOTE_LLM_KEY", "")
        or os.environ.get("DEEPSEEK_API_KEY", "")
    ).strip()
    if not key:
        raise LlmError(
            "缺少 LLM API Key。在左侧「下载」页填写，或设置环境变量 VIDNOTE_LLM_KEY。"
        )
    return key


def _base_url(value: str | None = None) -> str:
    base = (
        (value or "").strip()
        or os.environ.get("VIDNOTE_LLM_BASE", "").strip()
        or DEFAULT_BASE
    )
    return base.rstrip("/")


def _model_name(value: str | None = None) -> str:
    return (
        (value or "").strip()
        or os.environ.get("VIDNOTE_LLM_MODEL", "").strip()
        or DEFAULT_MODEL
    )


def endpoint(base_url: str | None = None) -> str:
    base = _base_url(base_url)
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


def _message_text(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        raise LlmError("LLM 没有返回内容。")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict)
        )
    text = str(content or "").strip()
    if not text:
        raise LlmError("LLM 返回了空内容。")
    return text


def chat(
    messages: list[dict],
    *,
    key: str,
    base_url: str | None = None,
    model: str | None = None,
    client: httpx.Client | None = None,
    retry_delay: float = 1.0,
) -> str:
    """调用 OpenAI 兼容的 chat/completions，返回正文。"""
    url = endpoint(base_url)
    selected = _model_name(model)
    owned = client is None
    active = client or httpx.Client(
        timeout=httpx.Timeout(180.0, connect=20.0), proxy=system_proxy()
    )
    body = {
        "model": selected,
        "messages": messages,
        "temperature": 0.2,
        "stream": False,
    }
    try:
        for attempt in range(3):
            try:
                response = active.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            except httpx.HTTPError as exc:
                raise LlmError(
                    f"连不上 LLM（{exc}）。检查接口地址、网络或代理设置。"
                ) from exc
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
                raise LlmError(
                    f"LLM 返回了无法解析的内容（HTTP {response.status_code}）"
                ) from exc
            if response.status_code >= 400:
                error = data.get("error") if isinstance(data, dict) else None
                message = (
                    error.get("message")
                    if isinstance(error, dict)
                    else str(error or response.text[:200])
                )
                raise LlmError(f"LLM API 错误（HTTP {response.status_code}）：{message}")
            return _message_text(data)
        raise LlmError("LLM 连续失败，请稍后重试。")
    finally:
        if owned:
            active.close()


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


def _mmss(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _chunk_cues(cues: list[Cue]) -> list[tuple[int, list[Cue]]]:
    chunks: list[tuple[int, list[Cue]]] = []
    start = 0
    chars = 0
    for index, cue in enumerate(cues):
        if index > start and (
            index - start >= _CHUNK_CUES or chars + len(cue.text) > _CHUNK_CHARS
        ):
            chunks.append((start, cues[start:index]))
            start = index
            chars = 0
        chars += len(cue.text)
    if start < len(cues):
        chunks.append((start, cues[start:]))
    return chunks


def _prompt(meta: VideoMeta, chunk: list[Cue]) -> str:
    context = [f"视频：《{meta.title}》", f"UP 主：{meta.owner}"]
    if meta.tags:
        context.append(f"标签：{'、'.join(meta.tags[:8])}")
    lines = context + ["", "转写（编号. (时间) 文本）："]
    for index, cue in enumerate(chunk):
        lines.append(f"{index}. ({_mmss(cue.start)}) {cue.text}")
    lines += ["", _SCHEMA_HINT]
    return "\n".join(lines)


def _index(item: dict) -> int | None:
    value = item.get("i", item.get("index"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _apply_chunk(
    payload: dict,
    *,
    start: int,
    chunk: list[Cue],
    texts: dict[int, str],
    points: list[KeyPoint],
) -> None:
    segments = payload.get("segments")
    if isinstance(segments, list):
        for item in segments:
            if not isinstance(item, dict):
                continue
            local = _index(item)
            if local is None or not 0 <= local < len(chunk):
                continue
            text = str(item.get("text") or "").strip()
            if text:
                texts[start + local] = text

    raw_points = payload.get("points")
    if isinstance(raw_points, list):
        for item in raw_points:
            if not isinstance(item, dict):
                continue
            local = _index(item)
            if local is None or not 0 <= local < len(chunk):
                continue
            title = str(item.get("title") or "").strip()[:24]
            detail = str(item.get("detail") or "").strip()[:80]
            if not title and not detail:
                continue
            points.append(
                KeyPoint(seconds=chunk[local].start, title=title, detail=detail)
            )


def _summary(
    points: list[KeyPoint],
    meta: VideoMeta,
    *,
    key: str,
    base_url: str | None,
    model: str | None,
) -> str:
    if not points:
        return ""
    lines = [f"{_mmss(point.seconds)} {point.title}：{point.detail}" for point in points]
    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {
            "role": "user",
            "content": f"视频：《{meta.title}》\n要点：\n" + "\n".join(lines),
        },
    ]
    return chat(messages, key=key, base_url=base_url, model=model).strip()


def refine_cues(
    cues: list[Cue],
    meta: VideoMeta,
    *,
    api_key_value: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
) -> Refined:
    """逐段精修文字，并生成摘要和带时间戳的要点。

    单段失败不会丢掉整篇笔记：保留原文字，把错误记在 ``Refined.errors``。
    """
    if not cues:
        return Refined(cues=[])

    key = api_key(api_key_value)
    selected = _model_name(model)
    chunks = _chunk_cues(cues)
    texts: dict[int, str] = {}
    points: list[KeyPoint] = []
    errors: list[str] = []
    done = 0

    for number, (start, chunk) in enumerate(chunks):
        if on_status:
            on_status(f"正在用 {selected} 精修第 {number + 1}/{len(chunks)} 段…")
        try:
            answer = chat(
                [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": _prompt(meta, chunk)},
                ],
                key=key,
                base_url=base_url,
                model=selected,
            )
            payload = _extract_json(answer)
            if payload is None:
                raise LlmError("返回内容不是 JSON")
            _apply_chunk(payload, start=start, chunk=chunk, texts=texts, points=points)
        except LlmError as exc:
            errors.append(f"第 {number + 1} 段：{exc}")
        done += len(chunk)
        if on_progress:
            on_progress(float(done), float(len(cues)))

    refined = [
        Cue(start=cue.start, end=cue.end, text=texts.get(index, cue.text))
        for index, cue in enumerate(cues)
    ]

    summary = ""
    if on_status and points:
        on_status("正在生成摘要…")
    try:
        summary = _summary(
            points, meta, key=key, base_url=base_url, model=selected
        )
    except LlmError as exc:
        errors.append(f"摘要：{exc}")

    changed = any(
        texts.get(index) not in (None, cue.text) for index, cue in enumerate(cues)
    )
    return Refined(
        cues=refined,
        summary=summary,
        points=points,
        model=selected,
        changed=changed,
        errors=errors,
    )
