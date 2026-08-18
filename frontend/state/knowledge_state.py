import asyncio
import logging
import time
from typing import Any

import reflex as rx

from frontend.state.error_handling import log_state_exception

logger = logging.getLogger(__name__)


class KnowledgeState(rx.State):
    """Knowledge DB 用の状態管理クラス"""

    mode: str = "list"  # "list", "add", "edit"

    # 知識一覧データ
    items: list[dict[str, Any]] = []
    is_loading: bool = False
    error_msg: str = ""
    success_msg: str = ""
    pending_delete_id: str = ""
    last_deleted_item: dict[str, Any] = {}
    undo_expires_at: float = 0.0

    # 追加用ステート
    input_type: str = "text"
    text_content: str = ""
    url_input: str = ""
    extracted_content: str = ""
    is_extracting: bool = False
    is_saving: bool = False
    source_revision: int = 0
    extracted_revision: int = -1
    extract_request_id: int = 0

    edit_id: str = ""
    edit_title: str = ""
    edit_summary: str = ""
    edit_original: str = ""

    def set_input_type(self, val: str):
        self.input_type = val
        self._invalidate_extraction()

    def set_text_content(self, val: str):
        self.text_content = val
        self._invalidate_extraction()

    def set_url_input(self, val: str):
        self.url_input = val
        self._invalidate_extraction()

    def _invalidate_extraction(self):
        self.source_revision += 1
        self.extract_request_id += 1
        self.extracted_revision = -1
        self.extracted_content = ""
        self.is_extracting = False

    def set_edit_title(self, val: str):
        self.edit_title = val

    def set_edit_summary(self, val: str):
        self.edit_summary = val

    def set_mode(self, mode: str):
        self.mode = mode
        if mode == "list":
            return KnowledgeState.load_items
        elif mode == "add":
            self.input_type = "text"
            self.text_content = ""
            self.url_input = ""
            self.extracted_content = ""
            self.extracted_revision = -1

    async def load_items(self):
        async for update in self._load_items_impl():
            yield update

    async def load_items_for_route(self):
        if not _personal_data_route_enabled():
            self.items = []
            self.is_loading = False
            self.error_msg = ""
            return
        async for update in self._load_items_impl():
            yield update

    async def _load_items_impl(self):
        self.is_loading = True
        self.error_msg = ""
        yield
        try:
            from src.knowledge_storage import load_all_knowledge_result

            result = await asyncio.to_thread(load_all_knowledge_result)
            if not result.is_available:
                self.error_msg = result.warnings[0]
                return
            db_items = result.data
            # Serialize for Reflex
            self.items = [
                {
                    "id": item.id,
                    "title": item.title,
                    "summary": item.summary,
                    "source_type": item.source_type,
                    "metadata": str(item.metadata) if item.metadata else "",
                    "created_at": item.created_at[:10],
                }
                for item in db_items
            ]
        except Exception as e:
            self.error_msg = log_state_exception(
                logger, "参照知識の読み込み", e
            ).message
        finally:
            self.is_loading = False
            yield

    async def delete_item(self, item_id: str):
        self.error_msg = ""
        self.success_msg = ""
        if self.pending_delete_id != item_id:
            self.pending_delete_id = item_id
            self.error_msg = "もう一度「削除を確定」を押すと削除します。"
            return
        try:
            from src.knowledge_storage import delete_knowledge, get_knowledge_by_id

            item = await asyncio.to_thread(get_knowledge_by_id, item_id)
            if item is None:
                raise ValueError("削除対象が存在しません")
            deleted = await asyncio.to_thread(delete_knowledge, item_id)
            if not deleted:
                raise ValueError("削除対象が存在しないか、削除に失敗しました")
            self.pending_delete_id = ""
            self.last_deleted_item = item.to_dict()
            self.undo_expires_at = time.monotonic() + 30.0
            self.success_msg = "参照知識を削除しました。30秒以内なら元に戻せます。"
            return KnowledgeState.load_items
        except Exception as e:
            self.error_msg = log_state_exception(logger, "参照知識の削除", e).message

    async def undo_delete(self):
        """Restore the last deleted item within the short undo window."""

        if not self.last_deleted_item or time.monotonic() > self.undo_expires_at:
            self.last_deleted_item = {}
            self.error_msg = "元に戻せる時間を過ぎました。"
            return
        try:
            from src.knowledge_storage import KnowledgeItem, save_knowledge

            restored = dict(self.last_deleted_item)
            restored["metadata"] = dict(restored.get("metadata") or {})
            item = KnowledgeItem.from_dict(restored)
            if not await asyncio.to_thread(save_knowledge, item):
                raise ValueError("復元保存に失敗しました")
            self.last_deleted_item = {}
            self.undo_expires_at = 0.0
            self.success_msg = "削除した参照知識を元に戻しました。"
            return KnowledgeState.load_items
        except Exception as e:
            self.error_msg = log_state_exception(logger, "参照知識の復元", e).message

    def prepare_edit(self, item_id: str):
        from src.knowledge_storage import get_knowledge_by_id

        item = get_knowledge_by_id(item_id)
        if item:
            self.edit_id = item.id
            self.edit_title = item.title
            self.edit_summary = item.summary
            self.edit_original = item.original_content
            self.mode = "edit"

    async def save_edit(self):
        self.error_msg = ""
        self.success_msg = ""
        try:
            from src.knowledge_storage import update_knowledge

            updates = {"title": self.edit_title, "summary": self.edit_summary}
            updated = await asyncio.to_thread(update_knowledge, self.edit_id, updates)
            if updated is None:
                raise ValueError("更新対象が存在しないか、更新に失敗しました")
            self.mode = "list"
            self.success_msg = "参照知識を更新しました。"
            return KnowledgeState.load_items
        except Exception as e:
            self.error_msg = log_state_exception(logger, "参照知識の更新", e).message

    async def extract_content(self):
        self.extract_request_id += 1
        request_id = self.extract_request_id
        revision = self.source_revision
        input_type = self.input_type
        text_content = self.text_content
        url_input = self.url_input
        self.is_extracting = True
        self.extracted_content = ""
        self.error_msg = ""
        yield

        try:
            from src.knowledge_extractor import extract_from_url, extract_from_youtube

            if input_type == "text":
                content = text_content
            elif input_type == "url":
                content = await asyncio.to_thread(extract_from_url, url_input)
            elif input_type == "youtube":
                content = await asyncio.to_thread(extract_from_youtube, url_input)
            else:
                content = ""
            if (
                request_id != self.extract_request_id
                or revision != self.source_revision
            ):
                return
            self.extracted_content = content
            self.extracted_revision = revision
        except Exception as e:
            self.error_msg = log_state_exception(logger, "コンテンツ抽出", e).message
        finally:
            if request_id == self.extract_request_id:
                self.is_extracting = False
            yield

    async def save_new_knowledge(self):
        if (
            not self.extracted_content
            or self.extracted_revision != self.source_revision
        ):
            self.error_msg = "入力内容を抽出し直してから保存してください"
            return
        if self.extracted_content.startswith("["):
            self.error_msg = "抽出に成功した内容がありません"
            return

        revision = self.source_revision
        content = self.extracted_content
        input_type = self.input_type
        url_input = self.url_input

        self.is_saving = True
        self.error_msg = ""
        self.success_msg = ""
        yield

        try:
            from src.knowledge_extractor import generate_title, summarize_content
            from src.knowledge_storage import KnowledgeItem, save_knowledge

            summary = await asyncio.to_thread(summarize_content, content, input_type)
            title = await asyncio.to_thread(generate_title, content, input_type)

            if revision != self.source_revision:
                self.error_msg = "入力内容が変更されたため保存を中止しました"
                return

            metadata = {}
            if input_type == "url":
                metadata["page_url"] = url_input
            elif input_type == "youtube":
                metadata["video_url"] = url_input

            item = KnowledgeItem.create(
                title=title,
                source_type=input_type,
                original_content=content,
                summary=summary,
                metadata=metadata,
            )
            saved = await asyncio.to_thread(save_knowledge, item)
            if not saved:
                raise ValueError("参照知識の保存に失敗しました")

            self.mode = "list"
            self.success_msg = "参照知識を追加しました。"
            yield KnowledgeState.load_items
        except Exception as e:
            self.error_msg = log_state_exception(logger, "参照知識の保存", e).message
        finally:
            self.is_saving = False
            yield

    async def handle_upload(self, files: list[rx.UploadFile]):
        """File upload handler"""
        self.extract_request_id += 1
        request_id = self.extract_request_id
        revision = self.source_revision
        self.is_extracting = True
        yield

        try:
            from pathlib import Path

            from src.knowledge_extractor import (
                MAX_UPLOAD_BYTES,
                SUPPORTED_FILE_EXTENSIONS,
                extract_from_file,
            )

            if files:
                file = files[0]
                extension = Path(file.filename or "").suffix.lower()
                if extension not in SUPPORTED_FILE_EXTENSIONS:
                    self.extracted_content = f"[未対応のファイル形式: {extension}]"
                    return
                upload_data = await file.read(MAX_UPLOAD_BYTES + 1)
                if len(upload_data) > MAX_UPLOAD_BYTES:
                    self.extracted_content = f"[ファイルサイズ上限は{MAX_UPLOAD_BYTES // (1024 * 1024)}MBです]"
                    return
                content = await asyncio.to_thread(
                    extract_from_file, upload_data, file.filename
                )
                if (
                    request_id != self.extract_request_id
                    or revision != self.source_revision
                ):
                    return
                self.extracted_content = content
                self.extracted_revision = revision
        except Exception as e:
            error = log_state_exception(logger, "ファイル内容の抽出", e)
            self.extracted_content = f"[エラー] {error.message}"
        finally:
            if request_id == self.extract_request_id:
                self.is_extracting = False
            yield


def _personal_data_route_enabled() -> bool:
    from src.app_mode import personal_data_enabled

    return personal_data_enabled()
