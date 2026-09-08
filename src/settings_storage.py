"""Environment-only API configuration for the research application."""

import os

from dotenv import load_dotenv

load_dotenv()


def get_gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "")


def get_finnhub_api_key() -> str:
    return os.environ.get("FINNHUB_API_KEY", "")


def get_edinet_api_key() -> str:
    return os.environ.get("EDINET_API_KEY", "")


def get_jquants_api_key() -> str:
    return os.environ.get("JQUANTS_API_KEY", "")
