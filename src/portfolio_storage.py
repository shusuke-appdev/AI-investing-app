"""
ポートフォリオ保存・読み込みモジュール
ローカルJSON または Supabase経由でポートフォリオを管理します。
（Strategyパターンによるリファクタリング適用済）
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from src.app_mode import require_writes_enabled
from src.log_config import get_logger
from src.storage.atomic_json import delete_file, read_json, update_json
from src.storage.base import BaseStorage

from .supabase_client import get_supabase_client

logger = get_logger(__name__)

PORTFOLIO_DIR = Path(__file__).parent.parent / "data" / "portfolios"
StorageType = Literal["local", "supabase"]


def set_storage_type(storage_type: StorageType):
    """ストレージタイプを設定"""
    from src.settings_storage import set_storage_type_setting

    set_storage_type_setting(storage_type)


def get_storage_type() -> StorageType:
    """現在のストレージタイプを取得"""
    from src.settings_storage import get_storage_type as _get_st

    return _get_st()


@dataclass
class SavedPortfolio:
    """保存済みポートフォリオ"""

    name: str
    holdings: list[dict]
    created_at: str
    updated_at: str


def ensure_portfolio_dir():
    """ポートフォリオディレクトリを作成"""
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)


class LocalPortfolioStorage(BaseStorage):
    def _get_portfolio_path(self, name: str) -> Path:
        safe_name = name.replace("/", "_").replace("\\", "_")
        return PORTFOLIO_DIR / f"{safe_name}.json"

    def save(self, id: str, data: Any) -> bool:
        ensure_portfolio_dir()
        now = datetime.now().isoformat()
        filepath = self._get_portfolio_path(id)
        try:

            def replace(existing: Any) -> dict[str, Any]:
                existing = existing if isinstance(existing, dict) else {}
                return {
                    "name": id,
                    "holdings": data,
                    "created_at": existing.get("created_at", now),
                    "updated_at": now,
                }

            update_json(filepath, {}, replace)
            return True
        except Exception as e:
            logger.error(f"Local save error: {e}")
            return False

    def load(self, id: str) -> Any | None:
        filepath = self._get_portfolio_path(id)
        if not filepath.exists():
            return None
        try:
            return read_json(filepath, None)
        except Exception as e:
            logger.error(f"Local load error: {e}")
            return None

    def list_all(self) -> list[Any]:
        ensure_portfolio_dir()
        names = []
        for f in PORTFOLIO_DIR.glob("*.json"):
            try:
                data = read_json(f, {})
                names.append(data.get("name", f.stem))
            except Exception:
                names.append(f.stem)
        return sorted(names)

    def delete(self, id: str) -> bool:
        filepath = self._get_portfolio_path(id)
        try:
            return delete_file(filepath)
        except Exception as e:
            logger.error(f"Local delete error: {e}")
            return False


class SupabasePortfolioStorage(BaseStorage):
    def save(self, id: str, data: Any) -> bool:
        client = get_supabase_client()
        if not client:
            return False
        try:
            payload = {
                "name": id,
                "holdings": data,
                "updated_at": datetime.now().isoformat(),
            }
            client.table("portfolios").upsert(payload, on_conflict="name").execute()
            return True
        except Exception as e:
            logger.error(f"Supabase save error: {e}")
            return False

    def load(self, id: str) -> Any | None:
        client = get_supabase_client()
        if not client:
            return None
        try:
            response = client.table("portfolios").select("*").eq("name", id).execute()
            rows = response.data
            if not rows:
                return None
            row = dict(rows[0])  # type: ignore
            return {
                "name": row.get("name"),
                "holdings": row.get("holdings", []),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }
        except Exception as e:
            logger.error(f"Supabase load error: {e}")
            return None

    def list_all(self) -> list[Any]:
        client = get_supabase_client()
        if not client:
            return []
        try:
            response = client.table("portfolios").select("name").execute()
            names = set(
                str(r.get("name"))
                for r in response.data
                if isinstance(r, dict) and r.get("name")
            )
            return sorted(list(names))
        except Exception as e:
            logger.error(f"Supabase list error: {e}")
            return []

    def delete(self, id: str) -> bool:
        client = get_supabase_client()
        if not client:
            return False
        try:
            client.table("portfolios").delete().eq("name", id).execute()
            return True
        except Exception as e:
            logger.error(f"Supabase delete error: {e}")
            return False


class PortfolioStorageFactory:
    @staticmethod
    def get_storage(storage_type: StorageType) -> BaseStorage:
        if storage_type == "supabase":
            return SupabasePortfolioStorage()
        return LocalPortfolioStorage()


# 統合インターフェース
def save_portfolio(
    name: str, holdings: list[dict], storage: StorageType | None = None
) -> bool:
    require_writes_enabled()
    st_type = storage or get_storage_type()
    return PortfolioStorageFactory.get_storage(st_type).save(name, holdings)


def load_portfolio(name: str, storage: StorageType | None = None) -> dict | None:
    st_type = storage or get_storage_type()
    return PortfolioStorageFactory.get_storage(st_type).load(name)


def list_portfolios(storage: StorageType | None = None) -> list[str]:
    st_type = storage or get_storage_type()
    return PortfolioStorageFactory.get_storage(st_type).list_all()


def delete_portfolio(name: str, storage: StorageType | None = None) -> bool:
    require_writes_enabled()
    st_type = storage or get_storage_type()
    return PortfolioStorageFactory.get_storage(st_type).delete(name)
