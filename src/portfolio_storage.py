"""
ポートフォリオ保存・読み込みモジュール
ローカルJSON または GAS（Google Apps Script）経由でポートフォリオを管理します。
"""
import json
import os
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass
from datetime import datetime

from .gas_client import get_gas_client


PORTFOLIO_DIR = Path(__file__).parent.parent / "data" / "portfolios"
StorageType = Literal["local", "gas"]

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
# 統合インターフェース
# ============================================================

def save_portfolio(name: str, holdings: list[dict], storage: Optional[StorageType] = None) -> bool:
    """
    ポートフォリオを保存します。
    
    Args:
        name: ポートフォリオ名
        holdings: 保有銘柄リスト
        storage: ストレージタイプ（省略時はデフォルト使用）
    
    Returns:
        保存成功時True
    """
    st = storage or _storage_type
    if st == "gas":
        return _save_gas(name, holdings)
    return _save_local(name, holdings)


def load_portfolio(name: str, storage: Optional[StorageType] = None) -> Optional[dict]:
    """
    ポートフォリオを読み込みます。
    
    Args:
        name: ポートフォリオ名
        storage: ストレージタイプ（省略時はデフォルト使用）
    
    Returns:
        ポートフォリオデータ、または見つからない場合None
    """
    st = storage or _storage_type
    if st == "gas":
        return _load_gas(name)
    return _load_local(name)


def list_portfolios(storage: Optional[StorageType] = None) -> list[str]:
    """
    保存済みポートフォリオ一覧を取得します。
    
    Args:
        storage: ストレージタイプ（省略時はデフォルト使用）
    
    Returns:
        ポートフォリオ名のリスト
    """
    st = storage or _storage_type
    if st == "gas":
        return _list_gas()
    return _list_local()


def delete_portfolio(name: str, storage: Optional[StorageType] = None) -> bool:
    """
    ポートフォリオを削除します。
    
    Args:
        name: ポートフォリオ名
        storage: ストレージタイプ（省略時はデフォルト使用）
    
    Returns:
        削除成功時True
    """
    st = storage or _storage_type
    if st == "gas":
        return _delete_gas(name)
    return _delete_local(name)
