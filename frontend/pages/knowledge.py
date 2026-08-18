import reflex as rx

from frontend.components.ui_primitives import (
    empty_state,
    loading_state,
    page_header,
)
from frontend.state.knowledge_state import KnowledgeState
from frontend.template import template


def render_knowledge_item(item: dict) -> rx.Component:
    """知識アイテムの1行表示"""
    # item["source_type"] に応じてアイコンを変更

    # Reflexの機能制約により、辞書から直接条件分岐するのが複雑なので、単純にアイコンを固定するかcondを使用する。
    # ここではシンプルに default アイコンとして 'file' を使用し、判定する
    icon_name = rx.cond(
        item["source_type"] == "text",
        "file-text",
        rx.cond(
            item["source_type"] == "youtube",
            "youtube",
            rx.cond(item["source_type"] == "url", "globe", "file"),
        ),
    )

    return rx.card(
        rx.flex(
            rx.vstack(
                rx.icon(tag=icon_name, size=24, color=rx.color("indigo", 9)),
                rx.text(item["source_type"], size="1", color="gray"),
                align_items="center",
                width="60px",
            ),
            rx.divider(orientation="vertical"),
            rx.vstack(
                rx.heading(item["title"], size="4", as_="h3"),
                rx.text(item["summary"], size="2", color=rx.color("gray", 11)),
                rx.hstack(
                    rx.cond(
                        item["metadata"] != "",
                        rx.text(f"Meta: {item['metadata']}", size="1", color="gray"),
                        rx.text(""),
                    ),
                    rx.text(f"Created: {item['created_at']}", size="1", color="gray"),
                    spacing="4",
                ),
                align_items="start",
                width="100%",
                spacing="2",
            ),
            rx.vstack(
                rx.button(
                    rx.icon("pencil", size=16),
                    "編集",
                    size="2",
                    variant="surface",
                    on_click=lambda: KnowledgeState.prepare_edit(item["id"]),
                ),
                rx.button(
                    rx.icon("trash-2", size=16),
                    rx.cond(
                        KnowledgeState.pending_delete_id == item["id"],
                        "削除を確定",
                        "削除",
                    ),
                    size="2",
                    color_scheme="red",
                    variant="soft",
                    on_click=lambda: KnowledgeState.delete_item(item["id"]),
                ),
                align_items="end",
                spacing="2",
            ),
            width="100%",
            align=rx.breakpoints(initial="start", md="center"),
            direction=rx.breakpoints(initial="column", md="row"),
            spacing="4",
        ),
        width="100%",
        margin_bottom="1rem",
    )


def render_list_mode() -> rx.Component:
    """一覧モード"""
    return rx.vstack(
        rx.hstack(
            rx.heading("保存済み知識", size="5", as_="h2"),
            rx.spacer(),
            rx.button(
                rx.icon("plus"),
                "新しい知識を追加",
                color_scheme="indigo",
                on_click=lambda: KnowledgeState.set_mode("add"),
            ),
            width="100%",
            align_items="center",
            margin_bottom="1rem",
        ),
        rx.cond(
            KnowledgeState.is_loading,
            loading_state("保存済み知識を取得中..."),
            rx.cond(
                KnowledgeState.items.length() > 0,
                rx.vstack(
                    rx.text(
                        f"全 {KnowledgeState.items.length()} 件",
                        size="2",
                        color="gray",
                        margin_bottom="1rem",
                    ),
                    rx.foreach(KnowledgeState.items, render_knowledge_item),
                    width="100%",
                ),
                empty_state(
                    "参照知識がありません",
                    "新しい知識を追加すると、AI分析の参照コンテキストとして利用できます。",
                    "book-open",
                ),
            ),
        ),
        width="100%",
    )


def render_add_mode() -> rx.Component:
    """追加モード"""
    return rx.vstack(
        rx.heading("知識を追加", size="5", as_="h2", margin_bottom="1rem"),
        rx.text("入力方式", weight="bold", size="2"),
        rx.radio(
            ["text", "file", "youtube", "url"],
            value=KnowledgeState.input_type,
            on_change=KnowledgeState.set_input_type,
            direction="row",
            spacing="4",
            margin_bottom="1rem",
        ),
        rx.divider(margin_bottom="1rem"),
        rx.cond(
            KnowledgeState.input_type == "text",
            rx.text_area(
                placeholder="ここに投資に関するメモや記事の内容を貼り付けてください...",
                value=KnowledgeState.text_content,
                on_change=KnowledgeState.set_text_content,
                height="300px",
                width="100%",
            ),
        ),
        rx.cond(
            KnowledgeState.input_type == "youtube",
            rx.input(
                placeholder="https://www.youtube.com/watch?v=...",
                value=KnowledgeState.url_input,
                on_change=KnowledgeState.set_url_input,
                width="100%",
            ),
        ),
        rx.cond(
            KnowledgeState.input_type == "url",
            rx.input(
                placeholder="https://...",
                value=KnowledgeState.url_input,
                on_change=KnowledgeState.set_url_input,
                width="100%",
            ),
        ),
        rx.cond(
            KnowledgeState.input_type == "file",
            rx.vstack(
                rx.upload(
                    rx.vstack(
                        rx.button("Select File", color_scheme="indigo"),
                        rx.text("Drag and drop files here or click to select files"),
                        align_items="center",
                        padding="2em",
                    ),
                    id="knowledge_upload",
                    multiple=False,
                ),
                rx.button(
                    "Upload",
                    on_click=KnowledgeState.handle_upload(
                        rx.upload_files(upload_id="knowledge_upload")
                    ),
                ),
                width="100%",
                align_items="center",
            ),
        ),
        rx.cond(
            (KnowledgeState.input_type != "file")
            & (KnowledgeState.input_type != "text"),
            rx.button(
                "抽出する",
                on_click=KnowledgeState.extract_content,
                loading=KnowledgeState.is_extracting,
                margin_top="1rem",
            ),
        ),
        rx.cond(
            KnowledgeState.input_type == "text",
            rx.button(
                "プレビュー更新",
                on_click=KnowledgeState.extract_content,
                loading=KnowledgeState.is_extracting,
                margin_top="1rem",
            ),
        ),
        rx.cond(
            KnowledgeState.extracted_content != "",
            rx.box(
                rx.text(
                    "プレビュー",
                    weight="bold",
                    margin_top="2rem",
                    margin_bottom="0.5rem",
                ),
                rx.text_area(
                    value=KnowledgeState.extracted_content,
                    read_only=True,
                    height="150px",
                    width="100%",
                ),
                width="100%",
            ),
        ),
        rx.divider(margin_top="2rem", margin_bottom="1rem"),
        rx.hstack(
            rx.button(
                rx.icon("database-zap", size=15),
                "AI参照に追加",
                color_scheme="indigo",
                on_click=KnowledgeState.save_new_knowledge,
                loading=KnowledgeState.is_saving,
                disabled=KnowledgeState.extracted_content == "",
            ),
            rx.button(
                "キャンセル",
                variant="surface",
                on_click=lambda: KnowledgeState.set_mode("list"),
            ),
            spacing="4",
        ),
        width="100%",
        max_width="800px",
    )


def render_edit_mode() -> rx.Component:
    """編集モード"""
    return rx.vstack(
        rx.heading("知識を編集", size="5", as_="h2", margin_bottom="1rem"),
        rx.text("タイトル", weight="bold", size="2"),
        rx.input(
            value=KnowledgeState.edit_title,
            on_change=KnowledgeState.set_edit_title,
            width="100%",
            margin_bottom="1rem",
        ),
        rx.text("要約 (AIが参照する内容)", weight="bold", size="2"),
        rx.text_area(
            value=KnowledgeState.edit_summary,
            on_change=KnowledgeState.set_edit_summary,
            height="200px",
            width="100%",
            margin_bottom="1rem",
        ),
        rx.text("元のコンテンツ", weight="bold", size="2"),
        rx.text_area(
            value=KnowledgeState.edit_original,
            read_only=True,
            height="150px",
            width="100%",
            margin_bottom="2rem",
        ),
        rx.hstack(
            rx.button(
                rx.icon("save", size=15),
                "更新を保存",
                color_scheme="indigo",
                on_click=KnowledgeState.save_edit,
            ),
            rx.button(
                "キャンセル",
                variant="surface",
                on_click=lambda: KnowledgeState.set_mode("list"),
            ),
            spacing="4",
        ),
        width="100%",
        max_width="800px",
    )


@template
def knowledge() -> rx.Component:
    """Knowledge DB ページ"""
    return rx.vstack(
        page_header(
            "参照知識管理",
            "AI分析が参照する知識ソースを追加・編集・削除します。",
        ),
        rx.cond(
            KnowledgeState.success_msg != "",
            rx.hstack(
                rx.callout(
                    KnowledgeState.success_msg,
                    icon="check",
                    color_scheme="green",
                    width="100%",
                ),
                rx.cond(
                    KnowledgeState.last_deleted_item.length() > 0,
                    rx.button("元に戻す", on_click=KnowledgeState.undo_delete),
                ),
                width="100%",
            ),
        ),
        rx.cond(
            KnowledgeState.error_msg != "",
            rx.callout(
                KnowledgeState.error_msg,
                icon="triangle-alert",
                color_scheme="red",
                width="100%",
            ),
        ),
        rx.cond(
            KnowledgeState.mode == "list",
            render_list_mode(),
            rx.cond(
                KnowledgeState.mode == "add", render_add_mode(), render_edit_mode()
            ),
        ),
        width="100%",
        max_width="1200px",
        margin="0 auto",
    )
