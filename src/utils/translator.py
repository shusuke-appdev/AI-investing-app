"""
Translation Utility Module
Uses Gemini API to translate text to Japanese.
"""

import google.generativeai as genai
import streamlit as st
from src.constants import GEMINI_MODEL_NAME
from src.log_config import get_logger
from src.settings_storage import get_gemini_api_key

logger = get_logger(__name__)

def _get_translator_model():
    """Gets or creates a Gemini model instance for translation."""
    api_key = get_gemini_api_key()
    if not api_key:
        logger.warning("Gemini API Key not found for translation.")
        return None
    
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(GEMINI_MODEL_NAME)

def translate_to_japanese(text: str) -> str:
    """
    Translates the given text to Japanese using Gemini.
    If the text is empty or appears to be Japanese already, returns original.
    """
    if not text or text.strip() == "情報なし":
        return text

    # Simple check if text contains Japanese characters (Hiragana, Katakana, Kanban)
    # This is a heuristic; if significant JP characters exist, assume it's JP.
    # Unicode ranges: Hiragana 3040-309F, Katakana 30A0-30FF, CJK 4E00-9FFF
    has_japanese = any(
        "\u3040" <= char <= "\u309f" or
        "\u30a0" <= char <= "\u30ff" or
        "\u4e00" <= char <= "\u9fff"
        for char in text
    )
    
    if has_japanese:
        return text

    model = _get_translator_model()
    if not model:
        return text

    try:
        prompt = f"以下の英文を、投資家向けの自然な日本語に翻訳してください。要約はせず、完全な翻訳をお願いします。\n\nOrigin: {text}\n\nTranslated:"
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        logger.error(f"Translation failed: {e}")
    
    return text
