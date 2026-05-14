"""
Gemini Client Module
google.genai SDK のクライアントを一元管理します。
"""

from google import genai

from src.constants import GEMINI_MODEL_NAME
from src.log_config import get_logger
from src.settings_storage import get_gemini_api_key

logger = get_logger(__name__)

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client | None:
    """
    Gemini API クライアントを取得します。
    APIキーが設定されていない場合は None を返します。
    """
    global _client
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
    import time

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
