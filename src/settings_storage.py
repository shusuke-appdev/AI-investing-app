"""
Settings Storage Module
API設定やGAS URLなどをローカルに永続化します。
"""

import json
from pathlib import Path
from typing import Optional

from src.log_config import get_logger

from .supabase_client import get_supabase_client

logger = get_logger(__name__)


# 設定ファイルのパス（プロジェクト内のdataディレクトリ）
SETTINGS_DIR = Path(__file__).parent.parent / "data"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# メモリキャッシュ（ファイルI/O削減用）
_settings_cache: Optional[dict] = None


def _ensure_dir():
    """設定ディレクトリを作成"""
    SETTINGS_DIR.mkdir(exist_ok=True)


def load_settings(force_reload: bool = False) -> dict:
    """
    保存された設定を読み込みます。
    Localをベースに、Supabaseが有効ならマージします。
    キャッシュがある場合はファイルI/Oをスキップします。

    Args:
        force_reload: Trueの場合キャッシュを無視して再読み込み
    """
    global _settings_cache

    if _settings_cache is not None and not force_reload:
        return _settings_cache.copy()

    data = {}

    # 1. Local Load
    try:
        target_file = SETTINGS_FILE
        if not target_file.exists():
            cwd_file = Path("data/settings.json").resolve()
            if cwd_file.exists():
                target_file = cwd_file

        if target_file.exists():
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)

    except Exception as e:
        logger.info(f"設定読み込みエラー: {e}")

    # 2. Supabase Merge (if enabled locally)
    if data.get("storage_type") == "supabase":
        client = get_supabase_client()
        if client:
            try:
                res = client.table("user_settings").select("*").execute()
                for row in res.data:
                    data[row["key"]] = row["value"]
            except Exception as e:
                logger.error(f"Supabase settings load error: {e}")

    _settings_cache = data
    return _settings_cache.copy()


def save_settings(settings: dict) -> bool:
    """
    設定を保存します。保存後はキャッシュを無効化します。
    """
    global _settings_cache
    try:
        # 1. Local Save
        _ensure_dir()
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        # 2. Supabase Save (if enabled)
        if settings.get("storage_type") == "supabase":
            client = get_supabase_client()
            if client:
                upsert_data = [
                    {"key": k, "value": str(v), "updated_at": "now()"}
                    for k, v in settings.items()
                ]
                client.table("user_settings").upsert(upsert_data).execute()

        _settings_cache = settings.copy()
        return True
    except Exception as e:
        logger.info(f"設定保存エラー: {e}")
        _settings_cache = None
        return False


def get_setting(key: str, default=None):
    """
    特定の設定値を取得します。

    Args:
        key: 設定キー
        default: デフォルト値

    Returns:
        設定値
    """
    settings = load_settings()
    return settings.get(key, default)


def set_setting(key: str, value) -> bool:
    """
    特定の設定値を保存します。

    Args:
        key: 設定キー
        value: 設定値

    Returns:
        成功時True
    """
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)


# === 便利関数 ===


def get_gemini_api_key() -> str:
    """Gemini APIキーを取得（Streamlit secrets対応）"""
    # 1. Streamlit secretsから取得
    try:
        import streamlit as st

        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    # 2. ローカル設定から取得
    return get_setting("gemini_api_key", "")


def set_gemini_api_key(api_key: str) -> bool:
    """Gemini APIキーを保存"""
    return set_setting("gemini_api_key", api_key)


def get_gas_url() -> str:
    """GAS Web App URLを取得（Streamlit secrets対応）"""
    # 1. Streamlit secretsから取得
    try:
        import streamlit as st

        if "GAS_WEBAPP_URL" in st.secrets:
            return st.secrets["GAS_WEBAPP_URL"]
    except Exception:
        pass
    # 2. ローカル設定から取得
    return get_setting("gas_url", "")


def set_gas_url(url: str) -> bool:
    """GAS Web App URLを保存"""
    return set_setting("gas_url", url)


def get_storage_type() -> str:
    """ストレージタイプを取得（local/gas）"""
    return get_setting("storage_type", "local")


def set_storage_type_setting(storage_type: str) -> bool:
    """ストレージタイプを保存"""
    return set_setting("storage_type", storage_type)


def get_finnhub_api_key() -> str:
    """Finnhub APIキーを取得（Streamlit secrets対応）"""
    # 1. Streamlit secretsから取得
    try:
        import streamlit as st

        if "FINNHUB_API_KEY" in st.secrets:
            return st.secrets["FINNHUB_API_KEY"]
    except Exception:
        pass
    # 2. ローカル設定から取得
    return get_setting("finnhub_api_key", "")


def set_finnhub_api_key(api_key: str) -> bool:
    """Finnhub APIキーを保存"""
    return set_setting("finnhub_api_key", api_key)
