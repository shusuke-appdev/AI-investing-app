"""
ポートフォリオ保存・読み込みモジュール
ローカルJSON または GAS（Google Apps Script）、Supabase経由でポートフォリオを管理します。
"""
import json
import os
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass
from datetime import datetime
import streamlit as st

try:
    from supabase import create_client, Client
except ImportError:
    Client = None

from .gas_client import get_gas_client


PORTFOLIO_DIR = Path(__file__).parent.parent / "data" / "portfolios"
StorageType = Literal["local", "gas", "supabase"]

# デフォルトストレージタイプ
_storage_type: StorageType = "local"


def set_storage_type(storage_type: StorageType):
    """ストレージタイプを設定"""
    global _storage_type
    _storage_type = storage_type


def get_storage_type() -> StorageType:
    """現在のストレージタイプを取得"""
    return _storage_type


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

def _save_local(name: str, holdings: list[dict]) -> bool:
    """ローカルJSONに保存"""
    ensure_portfolio_dir()
    now = datetime.now().isoformat()
    
    portfolio = {
        "name": name,
        "holdings": holdings,
        "created_at": now,
        "updated_at": now,
    }
    
    filename = PORTFOLIO_DIR / f"{name}.json"
    
    # 既存ファイルがあれば作成日時を保持
    if filename.exists():
        try:
            with open(filename, "r", encoding="utf-8") as f:
                existing = json.load(f)
                portfolio["created_at"] = existing.get("created_at", now)
        except:
            pass
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(portfolio, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving portfolio: {e}")
        return False


def _load_local(name: str) -> Optional[dict]:
    """ローカルJSONから読み込み"""
    filename = PORTFOLIO_DIR / f"{name}.json"
    
    if not filename.exists():
        return None
    
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading portfolio: {e}")
        return None


def _list_local() -> list[str]:
    """ローカルポートフォリオ一覧"""
    ensure_portfolio_dir()
    portfolios = []
    for f in PORTFOLIO_DIR.glob("*.json"):
        portfolios.append(f.stem)
    return sorted(portfolios)


def _delete_local(name: str) -> bool:
    """ローカルポートフォリオ削除"""
    filename = PORTFOLIO_DIR / f"{name}.json"
    if filename.exists():
        try:
            filename.unlink()
            return True
        except:
            return False
    return False


# ============================================================
# GASストレージ関数
# ============================================================

def _save_gas(name: str, holdings: list[dict]) -> bool:
    """GAS経由で保存"""
    client = get_gas_client()
    if not client:
        print("GAS client not configured")
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


# ============================================================
# Supabaseストレージ関数
# ============================================================

@st.cache_resource
def _get_supabase_client() -> Optional[Client]:
    """Supabaseクライアントを取得 (Cached)"""
    if 'supabase' not in globals() or not Client:
        return None
        
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    # Try Streamlit Secrets fallback
    if not url and hasattr(st, "secrets") and "SUPABASE_URL" in st.secrets:
        url = st.secrets["SUPABASE_URL"]
    if not key and hasattr(st, "secrets") and "SUPABASE_KEY" in st.secrets:
        key = st.secrets["SUPABASE_KEY"]

    if url and key:
        try:
            return create_client(url, key)
        except Exception as e:
            print(f"Supabase connection error: {e}")
            return None
    return None


def _save_supabase(name: str, holdings: list[dict]) -> bool:
    """Supabase経由で保存 (portfolio_sync update)"""
    client = _get_supabase_client()
    if not client:
        return False

    # Delete existing entries for this portfolio name logic is tricky if using upsert on composite key.
    # But since holdings might change (delete), best is to delete all for name then insert.
    try:
        # Transaction? Supabase-py doesn't support easy transactions yet.
        # Step 1: Delete all for this name
        client.table("portfolio_sync").delete().eq("name", name).execute()
        
        # Step 2: Insert new
        data = []
        for h in holdings:
            data.append({
                "name": name,
                "ticker": h.get("ticker"),
                "shares": float(h.get("shares", 0)),
                "avg_cost": float(h.get("avg_cost", 0)),
                "current_price": None, # Will be filled by sync agent or app logic
                "market_value": None,
                "unrealized_pl": None,
            })
        
        if data:
            client.table("portfolio_sync").insert(data).execute()
        return True
    except Exception as e:
        print(f"Supabase save error: {e}")
        return False


def _load_supabase(name: str) -> Optional[dict]:
    """Supabaseから読み込み"""
    client = _get_supabase_client()
    if not client:
        return None

    try:
        response = client.table("portfolio_sync").select("*").eq("name", name).execute()
        rows = response.data
        if not rows:
            return None
            
        holdings = []
        updated_at = datetime.now().isoformat()
        
        for row in rows:
            holdings.append({
                "ticker": row["ticker"],
                "shares": row["shares"],
                "avg_cost": row["avg_cost"]
            })
            if row.get("updated_at"):
                updated_at = row["updated_at"]
                
        return {
            "name": name,
            "holdings": holdings,
            "created_at": updated_at, # Approximate
            "updated_at": updated_at
        }
    except Exception as e:
        print(f"Supabase load error: {e}")
        return None


def _list_supabase() -> list[str]:
    """Supabaseからポートフォリオ名一覧"""
    client = _get_supabase_client()
    if not client:
        return []
    
    try:
        # Distinct names
        # Note: RPC or unique selector needed. simple logic:
        # This is inefficient for large tables, but okay for personal use
        response = client.table("portfolio_sync").select("name").execute()
        names = set(r["name"] for r in response.data)
        return sorted(list(names))
    except Exception as e:
        print(f"Supabase list error: {e}")
        return []


def _delete_supabase(name: str) -> bool:
    """Supabaseから削除"""
    client = _get_supabase_client()
    if not client:
        return False
    
    try:
        client.table("portfolio_sync").delete().eq("name", name).execute()
        return True
    except Exception as e:
        print(f"Supabase delete error: {e}")
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
