import asyncio
from typing import Any

import reflex as rx


class KnowledgeState(rx.State):
    """Knowledge DB 用の状態管理クラス"""

    mode: str = "list"  # "list", "add", "edit"

    # 知識一覧データ
    items: list[dict[str, Any]] = []
    is_loading: bool = False

    # 追加用ステート
    input_type: str = "text"
    text_content: str = ""
    url_input: str = ""
    extracted_content: str = ""
    is_extracting: bool = False
    is_saving: bool = False

    edit_id: str = ""
    edit_title: str = ""
    edit_summary: str = ""
    edit_original: str = ""

    def set_input_type(self, val: str):
        self.input_type = val

    def set_text_content(self, val: str):
        self.text_content = val

    def set_url_input(self, val: str):
        self.url_input = val

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

    async def load_items(self):
        self.is_loading = True
        yield
        try:
            from src.knowledge_storage import load_all_knowledge

            db_items = await asyncio.to_thread(load_all_knowledge)
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
        finally:
            self.is_loading = False
            yield

    async def delete_item(self, item_id: str):
        try:
            from src.knowledge_storage import delete_knowledge

            deleted = await asyncio.to_thread(delete_knowledge, item_id)
            if not deleted:
                raise ValueError("削除対象が存在しないか、削除に失敗しました")
            return KnowledgeState.load_items
        except Exception as e:
            print(f"Error deleting: {e}")

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
        try:
            from src.knowledge_storage import update_knowledge

            updates = {"title": self.edit_title, "summary": self.edit_summary}
            await asyncio.to_thread(update_knowledge, self.edit_id, updates)
            self.mode = "list"
            return KnowledgeState.load_items
        except Exception as e:
            print(f"Error updating: {e}")

    async def extract_content(self):
        self.is_extracting = True
        self.extracted_content = ""
        yield

        try:
            from src.knowledge_extractor import extract_from_url, extract_from_youtube

            if self.input_type == "text":
                self.extracted_content = self.text_content
            elif self.input_type == "url":
                self.extracted_content = await asyncio.to_thread(
                    extract_from_url, self.url_input
                )
            elif self.input_type == "youtube":
                self.extracted_content = await asyncio.to_thread(
                    extract_from_youtube, self.url_input
                )
        except Exception as e:
            self.extracted_content = f"[Error] {e}"
        finally:
            self.is_extracting = False
            yield

    async def save_new_knowledge(self):
        if not self.extracted_content or self.extracted_content.startswith("["):
            return

        self.is_saving = True
        yield

        try:
            from src.knowledge_extractor import generate_title, summarize_content
            from src.knowledge_storage import KnowledgeItem, save_knowledge

            summary = await asyncio.to_thread(
                summarize_content, self.extracted_content, self.input_type
            )
            title = await asyncio.to_thread(
                generate_title, self.extracted_content, self.input_type
            )

            metadata = {}
            if self.input_type == "url":
                metadata["page_url"] = self.url_input
            elif self.input_type == "youtube":
                metadata["video_url"] = self.url_input

            item = KnowledgeItem.create(
                title=title,
                source_type=self.input_type,
                original_content=self.extracted_content,
                summary=summary,
                metadata=metadata,
            )
            saved = await asyncio.to_thread(save_knowledge, item)
            if not saved:
                raise ValueError("参照知識の保存に失敗しました")

            self.mode = "list"
            yield KnowledgeState.load_items
        except Exception as e:
            print(f"Error saving new knowledge: {e}")
        finally:
            self.is_saving = False
            yield

    async def handle_upload(self, files: list[rx.UploadFile]):
        """File upload handler"""
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
                self.extracted_content = await asyncio.to_thread(
                    extract_from_file, upload_data, file.filename
                )
        except Exception as e:
            self.extracted_content = f"[Error] {e}"
        finally:
            self.is_extracting = False
            yield
