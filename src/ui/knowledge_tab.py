"""
Knowledge Management Tab Module
Manages the UI for viewing, adding, editing, and deleting reference knowledge.
"""

import streamlit as st

from src.knowledge_extractor import (
    extract_from_file,
    extract_from_url,
    extract_from_youtube,
    generate_title,
    summarize_content,
)
from src.knowledge_storage import (
    KnowledgeItem,
    delete_knowledge,
    get_knowledge_by_id,
    load_all_knowledge,
    save_knowledge,
    update_knowledge,
)


def render_knowledge_tab():
    """Renders the knowledge management tab."""
    st.title("📚 参照知識管理")
    st.markdown("AIチャットが参照する知識ソースを管理します。")

    # 知識追加モード切替
    if "knowledge_mode" not in st.session_state:
        st.session_state.knowledge_mode = "list"  # "list" | "add" | "edit"

    # モード別表示
    if st.session_state.knowledge_mode == "list":
        _render_knowledge_list()
    elif st.session_state.knowledge_mode == "add":
        _render_knowledge_add()
    elif st.session_state.knowledge_mode == "edit":
        _render_knowledge_edit()


def _render_knowledge_list():
    """知識一覧表示"""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("保存済み知識")
    with col2:
        if st.button(
            "➕ 新しい知識を追加",
            key="add_knowledge_btn_main",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.knowledge_mode = "add"
            st.rerun()

    items = load_all_knowledge()

    if not items:
        st.info(
            "まだ知識が追加されていません。「追加」ボタンから情報を登録してください。"
        )
        return

    st.markdown(f"全 {len(items)} 件")

    for item in items:
        source_icon = {"text": "📝", "file": "📄", "youtube": "🎥", "url": "🌐"}.get(
            item.source_type, "📌"
        )

        with st.container(border=True):
            cols = st.columns([1, 4, 1])
            with cols[0]:
                st.markdown(f"## {source_icon}")
                st.caption(item.source_type)

            with cols[1]:
                st.markdown(f"### {item.title}")
                st.markdown(item.summary)
                if item.metadata:
                    st.caption(f"Metadata: {item.metadata}")
                st.caption(f"作成日: {item.created_at[:10]}")

            with cols[2]:
                if st.button("✏️ 編集", key=f"edit_{item.id}", use_container_width=True):
                    st.session_state.knowledge_mode = "edit"
                    st.session_state.edit_knowledge_id = item.id
                    st.rerun()

                if st.button(
                    "🗑️ 削除",
                    key=f"del_{item.id}",
                    type="primary",
                    use_container_width=True,
                ):
                    delete_knowledge(item.id)
                    st.toast("削除しました", icon="🗑️")
                    st.rerun()


def _render_knowledge_add():
    """知識追加フォーム"""
    st.subheader("📥 知識を追加")

    # 入力タイプ選択
    input_type = st.radio(
        "入力方式",
        ["text", "file", "youtube", "url"],
        format_func=lambda x: {
            "text": "📝 テキスト",
            "file": "📄 ファイル",
            "youtube": "🎥 YouTube",
            "url": "🌐 URL",
        }[x],
        horizontal=True,
    )

    st.divider()

    content = ""
    metadata = {}

    if input_type == "text":
        content = st.text_area(
            "テキストを入力",
            height=300,
            placeholder="ここに投資に関するメモや記事の内容を貼り付けてください...",
        )

    elif input_type == "file":
        uploaded = st.file_uploader(
            "ファイルをアップロード",
            type=["txt", "pdf", "md", "csv", "json"],
            help="txt, pdf, md, csv, json形式に対応",
        )
        if uploaded:
            content = extract_from_file(uploaded.read(), uploaded.name)
            metadata["file_name"] = uploaded.name
            st.success(f"ファイル読み込み完了: {uploaded.name}")

    elif input_type == "youtube":
        url = st.text_input(
            "YouTube URL", placeholder="https://www.youtube.com/watch?v=..."
        )
        if url:
            with st.spinner("YouTubeからトランスクリプトを取得中..."):
                content = extract_from_youtube(url)
            metadata["video_url"] = url

    elif input_type == "url":
        url = st.text_input("Webページ URL", placeholder="https://...")
        if url:
            with st.spinner("Webページからコンテンツを取得中..."):
                content = extract_from_url(url)
            metadata["page_url"] = url

    # プレビュー
    if content:
        if content.startswith("["):
            st.error(content)
            content = ""  # エラーならクリア
        else:
            with st.expander("プレビューを確認", expanded=False):
                st.code(content[:1000] + ("..." if len(content) > 1000 else ""))
                st.caption(f"文字数: {len(content)}")

    st.divider()

    # ボタン
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(
            "💾 保存してAIに学習させる",
            type="primary",
            use_container_width=True,
            disabled=not content,
        ):
            with st.spinner("AIが内容を要約中..."):
                summary = summarize_content(content, input_type)
                title = generate_title(content, input_type)

            item = KnowledgeItem.create(
                title=title,
                source_type=input_type,
                original_content=content,
                summary=summary,
                metadata=metadata,
            )
            save_knowledge(item)
            st.toast(
                "✅ 知識を保存しました！AIチャットで利用可能になります。", icon="🎉"
            )
            st.session_state.knowledge_mode = "list"
            st.rerun()

    with col2:
        if st.button("キャンセル", use_container_width=True):
            st.session_state.knowledge_mode = "list"
            st.rerun()


def _render_knowledge_edit():
    """知識編集フォーム"""
    item_id = st.session_state.get("edit_knowledge_id")
    if not item_id:
        st.session_state.knowledge_mode = "list"
        st.rerun()
        return

    item = get_knowledge_by_id(item_id)
    if not item:
        st.warning("指定された知識が見つかりません")
        st.session_state.knowledge_mode = "list"
        st.rerun()
        return

    st.subheader("✏️ 知識を編集")

    col1, col2 = st.columns([2, 1])
    with col1:
        new_title = st.text_input("タイトル", value=item.title)
    with col2:
        st.write("")  # spacer
        st.caption(f"ID: {item.id[:8]}...")

    new_summary = st.text_area(
        "要約 (AIが参照する内容)", value=item.summary, height=200
    )

    st.caption(f"ソースタイプ: {item.source_type}")
    with st.expander("元のコンテンツを確認"):
        st.text(item.original_content)

    st.divider()

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("💾 更新を保存", type="primary", use_container_width=True):
            update_knowledge(item_id, {"title": new_title, "summary": new_summary})
            st.toast("✅ 更新しました", icon="💾")
            st.session_state.knowledge_mode = "list"
            st.rerun()

    with col2:
        if st.button("キャンセル", use_container_width=True):
            st.session_state.knowledge_mode = "list"
            st.rerun()
