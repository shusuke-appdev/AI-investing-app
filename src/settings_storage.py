"""
Settings Storage Module
API設定や保存先設定をローカルに永続化します。
"""

import os
from datetime import datetime, timezone
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
            loaded = read_json(target_file, {})
            data = loaded if isinstance(loaded, dict) else {}

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
    require_writes_enabled()
    try:
        # 1. Local Save
        _ensure_dir()
        write_json(SETTINGS_FILE, settings)

        # 2. Supabase Save (if enabled)
        if settings.get("storage_type") == "supabase":
            client = get_supabase_client()
            if client:
                upsert_data = [
                    {
                        "key": k,
                        "value": str(v),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
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
    """Gemini APIキーを取得（環境変数 → settings_storage）"""
    return os.environ.get("GEMINI_API_KEY", "")


def set_gemini_api_key(api_key: str) -> bool:
    """Gemini APIキー情報のUI経由保存はセキュリティ強化のため廃止されました"""
    return False


def get_storage_type() -> str:
    """ストレージタイプを取得（local/supabase）。旧GAS設定はlocalへ移行する。"""
    value = get_setting("storage_type", "local")
    return value if value in {"local", "supabase"} else "local"


def set_storage_type_setting(storage_type: str) -> bool:
    """ストレージタイプを保存"""
    if storage_type not in {"local", "supabase"}:
        raise ValueError("storage_type must be 'local' or 'supabase'.")
    return set_setting("storage_type", storage_type)


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
