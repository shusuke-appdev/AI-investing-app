"""
参照知識ストレージモジュール
ユーザーが提供した情報を保存・管理します。
"""
import json
import os
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional
from pathlib import Path


# データ保存ディレクトリ
DATA_DIR = Path(__file__).parent.parent / "data" / "knowledge"


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
    metadata: dict = field(default_factory=dict)  # URL, file_name, video_id等
    
    @classmethod
    def create(
        cls,
        title: str,
        source_type: str,
        original_content: str,
        summary: str,
        metadata: Optional[dict] = None
    ) -> "KnowledgeItem":
        """新しいKnowledgeItemを作成"""
        now = datetime.now().isoformat()
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            source_type=source_type,
            original_content=original_content[:10000],  # 最大10KB
            summary=summary,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
    
    def to_dict(self) -> dict:
        """辞書に変換"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeItem":
        """辞書から作成"""
        return cls(**data)


def _ensure_data_dir() -> None:
    """データディレクトリが存在することを確認"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_storage_path() -> Path:
    """ストレージファイルのパスを取得"""
    _ensure_data_dir()
    return DATA_DIR / "knowledge_items.json"


from src.settings_storage import get_storage_type
from src.gas_client import get_gas_client
from src.supabase_client import get_supabase_client
from src.log_config import get_logger

logger = get_logger(__name__)

def save_knowledge(item: KnowledgeItem) -> None:
    """
    参照知識を保存します。
    
    Args:
        item: 保存するKnowledgeItem
    """
    # GAS
    if get_storage_type() == "gas":
        client = get_gas_client()
        if client:
            client.save_knowledge_item(item.to_dict())
            return

    # Supabase
    if get_storage_type() == "supabase":
        client = get_supabase_client()
        if client:
            try:
                # Upsert
                # Supabase upsert requires dict.
                data = item.to_dict()
                # Ensure metadata is json compatible
                client.table("knowledge_items").upsert(data).execute()
                return
            except Exception as e:
                logger.error(f"Supabase save error: {e}")
                return

    # ローカルストレージの場合
    items = load_all_knowledge()
    
    # 既存アイテムの更新または新規追加
    existing_idx = next(
        (i for i, x in enumerate(items) if x.id == item.id),
        None
    )
    
    if existing_idx is not None:
        items[existing_idx] = item
    else:
        items.append(item)
    
    _save_all(items)


def load_all_knowledge() -> list[KnowledgeItem]:
    """
    全ての参照知識を読み込みます。
    
    Returns:
        KnowledgeItemのリスト（作成日時順）
    """
    # GASストレージの場合
    if get_storage_type() == "gas":
        client = get_gas_client()
        if client:
            try:
                data_list = client.get_all_knowledge()
                # 辞書からオブジェクトへ変換
                items = []
                for d in data_list:
                    try:
                        items.append(KnowledgeItem.from_dict(d))
                    except Exception as e:
                        logger.info(f"Skipping invalid item: {e}")
                
                # ソート (新しい順)
                items.sort(key=lambda x: x.created_at, reverse=True)
                return items
            except Exception as e:
                logger.error(f"GAS load error: {e}")
                return []

    # Supabase
    if get_storage_type() == "supabase":
        client = get_supabase_client()
        if client:
            try:
                res = client.table("knowledge_items").select("*").execute()
                items = []
                for d in res.data:
                    items.append(KnowledgeItem.from_dict(d))
                # Sort
                items.sort(key=lambda x: x.created_at, reverse=True)
                return items
            except Exception as e:
                logger.error(f"Supabase load error: {e}")
                return []

    # ローカルストレージの場合
    storage_path = _get_storage_path()
    
    if not storage_path.exists():
        return []
    
    try:
        with open(storage_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = [KnowledgeItem.from_dict(d) for d in data]
        # 作成日時でソート（新しい順）
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Knowledge storage read error: {e}")
        return []


def get_knowledge_by_id(item_id: str) -> Optional[KnowledgeItem]:
    """
    IDで参照知識を取得します。
    """
    items = load_all_knowledge()
    return next((x for x in items if x.id == item_id), None)


def delete_knowledge(item_id: str) -> bool:
    """
    参照知識を削除します。
    
    Args:
        item_id: 削除するアイテムのID
    
    Returns:
        削除成功時True
    """
    # GASストレージの場合
    if get_storage_type() == "gas":
        client = get_gas_client()
        if client:
            return client.delete_knowledge_item(item_id)
        return False

    # Supabase
    if get_storage_type() == "supabase":
        client = get_supabase_client()
        if client:
            try:
                client.table("knowledge_items").delete().eq("id", item_id).execute()
                return True
            except Exception as e:
                logger.error(f"Supabase delete error: {e}")
        return False

    # ローカルストレージの場合
    items = load_all_knowledge()
    original_len = len(items)
    items = [x for x in items if x.id != item_id]
    
    if len(items) < original_len:
        _save_all(items)
        return True
    return False


def update_knowledge(item_id: str, updates: dict) -> Optional[KnowledgeItem]:
    """
    参照知識を更新します。
    
    Args:
        item_id: 更新するアイテムのID
        updates: 更新内容（title, summary等）
    
    Returns:
        更新後のKnowledgeItem または None
    """
    item = get_knowledge_by_id(item_id)
    if not item:
        return None
    
    # 許可されたフィールドのみ更新
    allowed_fields = {"title", "summary", "metadata"}
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(item, key, value)
    
    item.updated_at = datetime.now().isoformat()
    save_knowledge(item)
    return item


def _save_all(items: list[KnowledgeItem]) -> None:
    """全アイテムを保存"""
    storage_path = _get_storage_path()
    data = [item.to_dict() for item in items]
    
    with open(storage_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_knowledge_for_ai_context(max_items: int = 10) -> str:
    """
    AI分析用のコンテキスト文字列を生成します。
    
    Args:
        max_items: 含める最大アイテム数
    
    Returns:
        フォーマット済みコンテキスト文字列
    """
    items = load_all_knowledge()[:max_items]
    
    if not items:
        return ""
    
    lines = ["【ユーザー参照知識】"]
    for item in items:
        source_label = {
            "text": "テキスト",
            "file": "ファイル",
            "youtube": "YouTube",
            "url": "URL"
        }.get(item.source_type, item.source_type)
        
        # 要約を200文字に制限
        summary_truncated = item.summary[:200]
        if len(item.summary) > 200:
            summary_truncated += "..."
        
        lines.append(f"- [{source_label}] {item.title}: {summary_truncated}")
    
    return "\n".join(lines)
