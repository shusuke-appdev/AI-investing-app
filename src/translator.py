"""
Translation Utility Module
Uses Gemini API to translate text to Japanese.
"""

from src.gemini_client import generate_content
from src.log_config import get_logger

logger = get_logger(__name__)


def translate_to_japanese(text: str) -> str:
    """
    Translates the given text to Japanese using Gemini.
    If the text is empty or appears to be Japanese already, returns original.
    """
    if not text or text.strip() == "情報なし":
        return text

    # Simple check if text contains Japanese characters (Hiragana, Katakana, CJK)
    has_japanese = any(
        "\u3040" <= char <= "\u309f"
        or "\u30a0" <= char <= "\u30ff"
        or "\u4e00" <= char <= "\u9fff"
        for char in text
    )

    if has_japanese:
        return text

    prompt = f"以下の英文を、投資家向けの自然な日本語に翻訳してください。要約はせず、完全な翻訳をお願いします。\n\nOrigin: {text[:8000]}\n\nTranslated:"
    result = generate_content(prompt)
    if result:
        return result.strip()

    return text
