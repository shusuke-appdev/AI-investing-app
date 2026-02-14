"""
ポートフォリオ保存・読み込みモジュール
ローカルJSON または GAS（Google Apps Script）、Supabase経由でポートフォリオを管理します。
"""
import json
import os
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    # Optional: gas_client check
    from .gas_client import get_gas_client
except ImportError:
    pass

from .supabase_client import get_supabase_client
from src.log_config import get_logger

logger = get_logger(__name__)

PORTFOLIO_DIR = Path(__file__).parent.parent / "data" / "portfolios"
StorageType = Literal["local", "gas", "supabase"]


def set_storage_type(storage_type: StorageType):
    """ストレージタイプを設定（session_stateで管理）"""
    import streamlit as st
    st.session_state["_storage_type"] = storage_type


def get_storage_type() -> StorageType:
    """現在のストレージタイプを取得"""
    import streamlit as st
    return st.session_state.get("_storage_type", "local")


@dataclass
class SavedPortfolio:
    """保存済みポートフォリオ"""
    name: str
    holdings: list[dict]  # [{"ticker": "AAPL", "shares": 10, "avg_cost": 150.0}, ...]
    created_at: str
    updated_at: str


def ensure_portfolio_dir():
    """ポートフォリオディレクトリを作成"""
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# ローカルストレージ関数
# ============================================================

def _get_portfolio_path(name: str) -> Path:
    """ポートフォリオファイルのパスを取得"""
    safe_name = name.replace("/", "_").replace("\\", "_")
    return PORTFOLIO_DIR / f"{safe_name}.json"


def _save_local(name: str, holdings: list[dict]) -> bool:
    """ローカルJSONに保存"""
    ensure_portfolio_dir()
    now = datetime.now().isoformat()
    filepath = _get_portfolio_path(name)

    # 既存ファイルがあれば created_at を保持
    created_at = now
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing = json.load(f)
                created_at = existing.get("created_at", now)
        except Exception:
            pass

    portfolio = {
        "name": name,
        "holdings": holdings,
        "created_at": created_at,
        "updated_at": now,
    }

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Local save error: {e}")
        return False


def _load_local(name: str) -> Optional[dict]:
    """ローカルJSONから読み込み"""
    filepath = _get_portfolio_path(name)
    if not filepath.exists():
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Local load error: {e}")
        return None


def _list_local() -> list[str]:
    """ローカルの全ポートフォリオ名を取得"""
    ensure_portfolio_dir()
    names = []
    for f in PORTFOLIO_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                names.append(data.get("name", f.stem))
        except Exception:
            names.append(f.stem)
    return sorted(names)


def _delete_local(name: str) -> bool:
    """ローカルJSONを削除"""
    filepath = _get_portfolio_path(name)
    if filepath.exists():
        try:
            filepath.unlink()
            return True
        except Exception as e:
            logger.error(f"Local delete error: {e}")
            return False
    return False


# ============================================================

def _save_gas(name: str, holdings: list[dict]) -> bool:
    """GAS経由で保存"""
    client = get_gas_client()
    if not client:
        logger.info("GAS client not configured")
        return False
    return client.save_portfolio(name, holdings)


def _load_gas(name: str) -> Optional[dict]:
    """GAS経由で読み込み"""
    client = get_gas_client()
    if not client:
        return None
    return client.load_portfolio(name)


def _list_gas() -> list[str]:
    """GAS経由で一覧取得"""
    client = get_gas_client()
    if not client:
        return []
    return client.list_portfolios()


def _delete_gas(name: str) -> bool:
    """GAS経由で削除"""
    client = get_gas_client()
    if not client:
        return False
    return client.delete_portfolio(name)


# Supabase Storage Functions
# Uses get_supabase_client from .supabase_client imported at top


def _save_supabase(name: str, holdings: list[dict]) -> bool:
    """Supabase経由で保存 (portfolios table)"""
    client = get_supabase_client()
    if not client:
        return False

    try:
        # Check if exists by name to get ID (or just upsert on name if unique constraint exists)
        # Schema defined name as unique.
        
        # Prepare payload
        current_time = datetime.now().isoformat()
        payload = {
            "name": name,
            "holdings": holdings, # JSONB conversion handled by client/library usually
            "updated_at": current_time
        }
        
        # Try upsert
        # Note: on_conflict="name" is needed if we rely on name uniqueness
        client.table("portfolios").upsert(payload, on_conflict="name").execute()
        return True
    except Exception as e:
        logger.error(f"Supabase save error: {e}")
        return False


def _load_supabase(name: str) -> Optional[dict]:
    """Supabaseから読み込み"""
    client = get_supabase_client()
    if not client:
        return None

    try:
        response = client.table("portfolios").select("*").eq("name", name).execute()
        rows = response.data
        if not rows:
            return None
            
        # Should be single row due to unique name
        row = rows[0]
        
        return {
            "name": row["name"],
            "holdings": row["holdings"], # Already list of dicts
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    except Exception as e:
        logger.error(f"Supabase load error: {e}")
        return None


def _list_supabase() -> list[str]:
    """Supabaseからポートフォリオ名一覧"""
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        # Distinct names
        response = client.table("portfolios").select("name").execute()
        names = set(r["name"] for r in response.data)
        return sorted(list(names))
    except Exception as e:
        logger.error(f"Supabase list error: {e}")
        return []


def _delete_supabase(name: str) -> bool:
    """Supabaseから削除"""
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        client.table("portfolios").delete().eq("name", name).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase delete error: {e}")
        return False


# ============================================================
# 統合インターフェース
# ============================================================

def save_portfolio(name: str, holdings: list[dict], storage: Optional[StorageType] = None) -> bool:
    """
    ポートフォリオを保存します。
    """
    st_type = storage or _storage_type
    if st_type == "gas":
        return _save_gas(name, holdings)
    elif st_type == "supabase":
        return _save_supabase(name, holdings)
    return _save_local(name, holdings)


def load_portfolio(name: str, storage: Optional[StorageType] = None) -> Optional[dict]:
    """
    ポートフォリオを読み込みます。
    """
    st_type = storage or _storage_type
    if st_type == "gas":
        return _load_gas(name)
    elif st_type == "supabase":
        return _load_supabase(name)
    return _load_local(name)


def list_portfolios(storage: Optional[StorageType] = None) -> list[str]:
    """
    保存済みポートフォリオ一覧を取得します。
    """
    st_type = storage or _storage_type
    if st_type == "gas":
        return _list_gas()
    elif st_type == "supabase":
        return _list_supabase()
    return _list_local()


def delete_portfolio(name: str, storage: Optional[StorageType] = None) -> bool:
    """
    ポートフォリオを削除します。
    """
    st_type = storage or _storage_type
    if st_type == "gas":
        return _delete_gas(name)
    elif st_type == "supabase":
        return _delete_supabase(name)
    return _delete_local(name)
