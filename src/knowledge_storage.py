"""
参照知識ストレージモジュール
ユーザーが提供した情報を保存・管理します。
（Strategyパターンによるリファクタリング適用済）
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.gas_client import get_gas_client
from src.log_config import get_logger
from src.settings_storage import get_storage_type
from src.storage.base import BaseStorage
from src.supabase_client import get_supabase_client

DATA_DIR = Path(__file__).parent.parent / "data" / "knowledge"

logger = get_logger(__name__)


@dataclass
class KnowledgeItem:
    """ユーザー参照知識のデータモデル"""

    id: str
    title: str
    source_type: str  # "text" | "file" | "youtube" | "url"
    original_content: str  # 元データ（最大10KB）
    summary: str  # AI抽出の概要
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        title: str,
        source_type: str,
        original_content: str,
        summary: str,
        metadata: dict | None = None,
    ) -> "KnowledgeItem":
        now = datetime.now().isoformat()
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            source_type=source_type,
            original_content=original_content[:10000],
            summary=summary,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeItem":
        return cls(**data)


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_storage_path() -> Path:
    _ensure_data_dir()
    return DATA_DIR / "knowledge_items.json"


class LocalKnowledgeStorage(BaseStorage):
    def save(self, id: str, data: Any) -> bool:
        items = self.list_all()
        # Ensure data is dict or KnowledgeItem
        item_dict = data if isinstance(data, dict) else data.to_dict()

        # update or insert
        existing_idx = next((i for i, x in enumerate(items) if x.get("id") == id), None)
        if existing_idx is not None:
            items[existing_idx] = item_dict
        else:
            items.append(item_dict)

        storage_path = _get_storage_path()
        with open(storage_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        return True

    def load(self, id: str) -> Any | None:
        items = self.list_all()
        return next((x for x in items if x.get("id") == id), None)

    def list_all(self) -> list[Any]:
        storage_path = _get_storage_path()
        if not storage_path.exists():
            return []
        try:
            with open(storage_path, encoding="utf-8") as f:
                data = json.load(f)
            # sort by created_at DESC
            data.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return data
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Knowledge storage read error: {e}")
            return []

    def delete(self, id: str) -> bool:
        items = self.list_all()
        original_len = len(items)
        items = [x for x in items if x.get("id") != id]
        if len(items) < original_len:
            storage_path = _get_storage_path()
            with open(storage_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            return True
        return False


class GasKnowledgeStorage(BaseStorage):
    def save(self, id: str, data: Any) -> bool:
        client = get_gas_client()
        if client:
            item_dict = data if isinstance(data, dict) else data.to_dict()
            client.save_knowledge_item(item_dict)
            return True
        return False

    def load(self, id: str) -> Any | None:
        items = self.list_all()
        return next((x for x in items if x.get("id") == id), None)

    def list_all(self) -> list[Any]:
        client = get_gas_client()
        if client:
            try:
                data_list = client.get_all_knowledge()
                data_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                return data_list
            except Exception as e:
                logger.error(f"GAS load error: {e}")
        return []

    def delete(self, id: str) -> bool:
        client = get_gas_client()
        if client:
            return client.delete_knowledge_item(id)
        return False


class SupabaseKnowledgeStorage(BaseStorage):
    def save(self, id: str, data: Any) -> bool:
        client = get_supabase_client()
        if client:
            try:
                item_dict = data if isinstance(data, dict) else data.to_dict()
                client.table("knowledge_items").upsert(item_dict).execute()
                return True
            except Exception as e:
                logger.error(f"Supabase save error: {e}")
        return False

    def load(self, id: str) -> Any | None:
        items = self.list_all()
        return next((x for x in items if x.get("id") == id), None)

    def list_all(self) -> list[Any]:
        client = get_supabase_client()
        if client:
            try:
                res = client.table("knowledge_items").select("*").execute()
                items: list[dict[str, Any]] = [
                    i for i in res.data if isinstance(i, dict)
                ]
                items.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
                return items
            except Exception as e:
                logger.error(f"Supabase load error: {e}")
        return []

    def delete(self, id: str) -> bool:
        client = get_supabase_client()
        if client:
            try:
                client.table("knowledge_items").delete().eq("id", id).execute()
                return True
            except Exception as e:
                logger.error(f"Supabase delete error: {e}")
        return False


class KnowledgeStorageFactory:
    @staticmethod
    def get_storage() -> BaseStorage:
        storage_type = get_storage_type()
        if storage_type == "gas":
            return GasKnowledgeStorage()
        elif storage_type == "supabase":
            return SupabaseKnowledgeStorage()
        return LocalKnowledgeStorage()


# 統合インターフェース


def save_knowledge(item: KnowledgeItem) -> None:
    storage = KnowledgeStorageFactory.get_storage()
    storage.save(item.id, item)


def load_all_knowledge() -> list[KnowledgeItem]:
    storage = KnowledgeStorageFactory.get_storage()
    data_list = storage.list_all()
    items = []
    for d in data_list:
        try:
            items.append(KnowledgeItem.from_dict(d))
        except Exception as e:
            logger.info(f"Skipping invalid item: {e}")
    return items


def get_knowledge_by_id(item_id: str) -> KnowledgeItem | None:
    storage = KnowledgeStorageFactory.get_storage()
    data = storage.load(item_id)
    if data:
        return KnowledgeItem.from_dict(data)
    return None


def delete_knowledge(item_id: str) -> bool:
    storage = KnowledgeStorageFactory.get_storage()
    return storage.delete(item_id)


def update_knowledge(item_id: str, updates: dict) -> KnowledgeItem | None:
    item = get_knowledge_by_id(item_id)
    if not item:
        return None

    allowed_fields = {"title", "summary", "metadata"}
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(item, key, value)

    item.updated_at = datetime.now().isoformat()
    save_knowledge(item)
    return item


def get_knowledge_for_ai_context(max_items: int = 10) -> str:
    items = load_all_knowledge()[:max_items]
    if not items:
        return ""

    lines = ["【ユーザー参照知識】"]
    for item in items:
        source_label = {
            "text": "テキスト",
            "file": "ファイル",
            "youtube": "YouTube",
            "url": "URL",
        }.get(item.source_type, item.source_type)

        summary_truncated = item.summary[:200]
        if len(item.summary) > 200:
            summary_truncated += "..."

        lines.append(f"- [{source_label}] {item.title}: {summary_truncated}")

    return "\n".join(lines)
