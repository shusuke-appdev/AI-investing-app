"""
Settings Storage Module
API設定や保存先設定をローカルに永続化します。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from src.app_mode import require_writes_enabled
from src.log_config import get_logger
from src.storage.atomic_json import read_json, write_json

from .supabase_client import get_supabase_client

# dotenv を用いて .env を環境変数にロードする。これはすべての関数を通して有効になる。
# インポート後に実行することで E402 を回避。
load_dotenv()

logger = get_logger(__name__)


# 設定ファイルのパス（プロジェクト内のdataディレクトリ）
SETTINGS_DIR = Path(__file__).parent.parent / "data"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# メモリキャッシュ（ファイルI/O削減用）
_settings_cache: dict | None = None


class StorageConfigurationError(RuntimeError):
    """Raised when a hosted deployment has no safe storage selection."""


def _ensure_dir():
    """設定ディレクトリを作成"""
    SETTINGS_DIR.mkdir(exist_ok=True)


def load_settings(force_reload: bool = False) -> dict:
    """
    保存されたローカル設定を読み込みます。
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
            loaded = read_json(target_file, {})
            data = loaded if isinstance(loaded, dict) else {}

    except Exception as e:
        logger.info(f"設定読み込みエラー: {e}")

    _settings_cache = data
    return _settings_cache.copy()


def save_settings(settings: dict) -> bool:
    """
    設定を保存します。保存後はキャッシュを無効化します。
    """
    global _settings_cache
    require_writes_enabled()
    try:
        _ensure_dir()
        write_json(SETTINGS_FILE, settings)
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
    """Gemini APIキーを取得（環境変数 → settings_storage）"""
    return os.environ.get("GEMINI_API_KEY", "")


def set_gemini_api_key(api_key: str) -> bool:
    """Gemini APIキー情報のUI経由保存はセキュリティ強化のため廃止されました"""
    return False


def get_storage_type() -> str:
    """Return the authoritative storage backend without remote bootstrap cycles."""

    configured = os.environ.get("APP_STORAGE_BACKEND", "").strip().lower()
    if configured:
        if configured not in {"local", "supabase"}:
            raise StorageConfigurationError(
                "APP_STORAGE_BACKEND must be 'local' or 'supabase'."
            )
        return configured
    if os.environ.get("SPACE_ID"):
        raise StorageConfigurationError(
            "Hosted personal-data storage is disabled until "
            "APP_STORAGE_BACKEND is explicitly configured."
        )
    value = get_setting("storage_type", "local")
    return value if value in {"local", "supabase"} else "local"


def set_storage_type_setting(storage_type: str) -> bool:
    """Validate the target backend before atomically changing local bootstrap state."""

    if storage_type not in {"local", "supabase"}:
        raise ValueError("storage_type must be 'local' or 'supabase'.")
    configured = os.environ.get("APP_STORAGE_BACKEND", "").strip()
    if configured:
        return configured == storage_type
    if storage_type == "supabase" and not _supabase_backend_ready():
        return False
    return set_setting("storage_type", storage_type)


def _supabase_backend_ready() -> bool:
    client = get_supabase_client()
    if client is None:
        return False
    try:
        for table in ("user_settings", "portfolios", "knowledge_items", "trade_plans"):
            client.table(table).select("*").limit(1).execute()
    except Exception as exc:
        logger.error("Supabase storage readiness failed: %s", exc)
        return False
    return True


def get_finnhub_api_key() -> str:
    """Finnhub APIキーを取得（環境変数）"""
    return os.environ.get("FINNHUB_API_KEY", "")


def set_finnhub_api_key(api_key: str) -> bool:
    """Finnhub APIキー情報のUI経由保存はセキュリティ強化のため廃止されました"""
    return False


def get_edinet_api_key() -> str:
    """EDINET APIキーを取得（環境変数）"""
    return os.environ.get("EDINET_API_KEY", "")


def get_jquants_api_key() -> str:
    """J-Quants API Key を取得（環境変数）"""
    return os.environ.get("JQUANTS_API_KEY", "")


def set_jquants_api_key(token: str) -> bool:
    """J-Quants APIキー情報のUI経由保存はセキュリティ強化のため廃止されました"""
    return False
