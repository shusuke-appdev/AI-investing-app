"""
Gemini Client Module
google.genai SDK のクライアントを一元管理します。
"""

from __future__ import annotations

import json
import time
from typing import Any, TypedDict

from google import genai

from src.app_mode import ai_generation_enabled, require_ai_generation_enabled
from src.constants import GEMINI_MODEL_NAME
from src.log_config import get_logger
from src.settings_storage import get_gemini_api_key

logger = get_logger(__name__)

_client: genai.Client | None = None


class GroundedCitation(TypedDict, total=False):
    """One URL citation returned by a grounded interaction."""

    url: str
    title: str
    start_index: int
    end_index: int


class GroundedGenerationResult(TypedDict, total=False):
    """Structured Gemini result with usage and grounding provenance."""

    status: str
    data: dict[str, Any]
    citations: list[GroundedCitation]
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    search_query_count: int
    warnings: list[str]
    error: str


def get_gemini_client() -> genai.Client | None:
    """
    Gemini API クライアントを取得します。
    APIキーが設定されていない場合は None を返します。
    """
    global _client
    if not ai_generation_enabled():
        return None
    if _client is not None:
        return _client

    api_key = get_gemini_api_key()
    if not api_key:
        return None

    _client = genai.Client(api_key=api_key)
    return _client


def configure_gemini(api_key: str | None = None) -> bool:
    """
    Gemini API クライアントを（再）設定します。

    Args:
        api_key: APIキー（省略時は settings_storage から取得）

    Returns:
        設定成功時 True
    """
    global _client
    if not ai_generation_enabled():
        return False
    key = api_key or get_gemini_api_key()
    if not key:
        return False

    _client = genai.Client(api_key=key)
    return True


def generate_content(
    prompt: str, model: str | None = None, max_retries: int = 3
) -> str | None:
    """
    Gemini API でコンテンツを生成します。
    429 (Rate Limit) / 503 (Service Unavailable) は指数バックオフでリトライします。

    Args:
        prompt: プロンプト文字列
        model: モデル名（省略時は GEMINI_MODEL_NAME）
        max_retries: 最大リトライ回数

    Returns:
        生成テキスト、または None
    """
    require_ai_generation_enabled()
    client = get_gemini_client()
    if client is None:
        return None

    model_name = model or GEMINI_MODEL_NAME
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            last_error = e
            error_str = str(e)
            # 429 (Rate Limit) / 503 (Service Unavailable) はリトライ対象
            is_retryable = any(
                code in error_str
                for code in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
            )
            if is_retryable and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                logger.warning(
                    f"Gemini API retryable error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s..."
                )
                time.sleep(wait)
                continue
            logger.error(f"Gemini generate_content error: {e}")
            return None

    logger.error(
        f"Gemini generate_content: max retries exhausted. Last error: {last_error}"
    )
    return None


def generate_grounded_structured(
    prompt: str,
    schema: dict[str, Any],
    *,
    model: str | None = None,
    max_retries: int = 3,
    timeout_seconds: float = 90,
) -> GroundedGenerationResult:
    """Run one search-grounded Interactions API request with a JSON schema.

    The caller still owns domain validation. This boundary only accepts URLs
    returned in interaction annotations as citations; URLs appearing only in
    model-authored JSON are not promoted to citations.
    """

    model_name = model or GEMINI_MODEL_NAME
    if not ai_generation_enabled():
        return _grounded_error(model_name, "AI生成が無効です。", "disabled")
    client = get_gemini_client()
    if client is None:
        return _grounded_error(
            model_name,
            "Gemini APIキーが未設定です。",
            "unconfigured",
        )

    last_error = ""
    for attempt in range(max_retries):
        try:
            interaction = client.interactions.create(
                model=model_name,
                input=prompt,
                tools=[{"type": "google_search"}],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema,
                },
                store=False,
                timeout=timeout_seconds,
            )
            text, citations, search_count = _interaction_evidence(interaction)
            usage = getattr(interaction, "usage", None)
            if not text:
                return _grounded_error(
                    model_name,
                    "構造化応答が空でした。",
                    "invalid_response",
                    citations=citations,
                    search_query_count=search_count,
                )
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                return _grounded_error(
                    model_name,
                    f"構造化応答をJSONとして解釈できません: {exc}",
                    "invalid_response",
                    citations=citations,
                    search_query_count=search_count,
                )
            if not isinstance(data, dict):
                return _grounded_error(
                    model_name,
                    "構造化応答のルートがオブジェクトではありません。",
                    "invalid_response",
                    citations=citations,
                    search_query_count=search_count,
                )
            warnings = [] if citations else ["検索引用を取得できませんでした。"]
            return {
                "status": "available",
                "data": data,
                "citations": citations,
                "model": str(getattr(interaction, "model", None) or model_name),
                "input_tokens": _usage_int(usage, "total_input_tokens"),
                "output_tokens": _usage_int(usage, "total_output_tokens"),
                "total_tokens": _usage_int(usage, "total_tokens"),
                "search_query_count": search_count,
                "warnings": warnings,
                "error": "",
            }
        except Exception as exc:
            last_error = str(exc)
            retryable = any(
                code in last_error
                for code in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
            )
            if retryable and attempt < max_retries - 1:
                wait_seconds = 2 ** (attempt + 1)
                logger.warning(
                    "Grounded Gemini retryable error (attempt %s/%s): %s",
                    attempt + 1,
                    max_retries,
                    exc,
                )
                time.sleep(wait_seconds)
                continue
            logger.warning("Grounded Gemini interaction failed: %s", exc)
            break
    return _grounded_error(model_name, last_error or "Gemini検索に失敗しました。")


def _interaction_evidence(
    interaction: Any,
) -> tuple[str, list[GroundedCitation], int]:
    texts: list[str] = []
    citations: list[GroundedCitation] = []
    seen_urls: set[str] = set()
    search_count = 0
    for step in list(getattr(interaction, "steps", None) or []):
        step_type = str(getattr(step, "type", ""))
        if step_type == "google_search_call":
            arguments = getattr(step, "arguments", None)
            queries = list(getattr(arguments, "queries", None) or [])
            search_count += len(queries) or 1
        if step_type != "model_output":
            continue
        for content in list(getattr(step, "content", None) or []):
            text_value = getattr(content, "text", None)
            if isinstance(text_value, str):
                texts.append(text_value)
            for annotation in list(getattr(content, "annotations", None) or []):
                url = str(getattr(annotation, "url", "") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                citations.append(
                    {
                        "url": url,
                        "title": str(getattr(annotation, "title", "") or ""),
                        "start_index": int(getattr(annotation, "start_index", 0) or 0),
                        "end_index": int(getattr(annotation, "end_index", 0) or 0),
                    }
                )
    return "".join(texts).strip(), citations, search_count


def _usage_int(usage: Any, name: str) -> int:
    try:
        return int(getattr(usage, name, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _grounded_error(
    model: str,
    error: str,
    status: str = "unavailable",
    *,
    citations: list[GroundedCitation] | None = None,
    search_query_count: int = 0,
) -> GroundedGenerationResult:
    return {
        "status": status,
        "data": {},
        "citations": citations or [],
        "model": model,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "search_query_count": search_query_count,
        "warnings": [],
        "error": error,
    }
