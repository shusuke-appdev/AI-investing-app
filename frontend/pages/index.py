import reflex as rx

from frontend.components.data_provenance import provenance_panel
from frontend.components.flash_summary import flash_summary
from frontend.components.ui_primitives import (
    loading_state,
    page_header,
    section_heading,
)
from frontend.state.market_state import MarketState
from frontend.template import template
from src.app_mode import ai_generation_enabled


@template
def index() -> rx.Component:
    """メインダッシュボード画面 (Market Intelligence)"""
    return rx.vstack(
        page_header(
            "Market Intelligence",
            "主要資産の変化、データ鮮度、AI市況整理を一つの画面で確認します。",
            rx.button(
                rx.icon("sparkles", size=18),
                "レポートを生成",
                on_click=MarketState.generate_ai_recap,
                loading=MarketState.is_generating_recap,
                color_scheme="indigo",
                size="3",
                variant="solid",
                disabled=not ai_generation_enabled(),
            ),
            rx.tooltip(
                rx.icon_button(
                    rx.icon("plus", size=16),
                    on_click=MarketState.toggle_recap_focus,
                    size="3",
                    variant="surface",
                    aria_label="任意の分析項目を追加",
                    disabled=not ai_generation_enabled(),
                ),
                content="任意の分析項目を追加",
            ),
            rx.button(
                rx.icon("refresh-cw", size=16),
                "概要更新",
                on_click=MarketState.fetch_market_summary_fast,
                loading=MarketState.is_fetching_summary,
                variant="surface",
            ),
        ),
        (
            rx.callout(
                "公開モードではAIレポート生成を利用できません。",
                icon="lock",
                color_scheme="amber",
                width="100%",
            )
            if not ai_generation_enabled()
            else rx.fragment()
        ),
        rx.cond(
            MarketState.recap_focus_visible,
            rx.card(
                rx.vstack(
                    rx.text("追加分析項目", weight="bold", size="2"),
                    rx.text_area(
                        value=MarketState.custom_recap_focus,
                        on_change=MarketState.set_custom_recap_focus,
                        placeholder="例: SaaS株の売りは構造悪化か、ナラティブ過剰反応かを分析",
                        width="100%",
                        min_height="92px",
                    ),
                    rx.hstack(
                        rx.spacer(),
                        rx.button(
                            rx.icon("sparkles", size=16),
                            "追加して生成",
                            on_click=MarketState.generate_ai_recap_with_focus,
                            loading=MarketState.is_generating_recap,
                            color_scheme="indigo",
                            disabled=not ai_generation_enabled(),
                        ),
                        width="100%",
                    ),
                    width="100%",
                    align_items="start",
                ),
                width="100%",
                margin_bottom="1rem",
            ),
        ),
        # エラーメッセージ
        rx.cond(
            MarketState.error_msg != "",
            rx.callout(
                MarketState.error_msg,
                icon="triangle_alert",
                color_scheme="red",
                margin_bottom="1rem",
                width="100%",
            ),
        ),
        # ローディングスピナー（全体）
        rx.cond(
            MarketState.is_fetching,
            loading_state("市場データを取得中..."),
            rx.vstack(
                provenance_panel(MarketState.provenance),
                rx.box(
                    section_heading(
                        "AI Market Recap",
                        "表示済みの市場コンテキストを再利用して市況を整理します。",
                    ),
                    rx.card(
                        rx.cond(
                            MarketState.ai_recap != "",
                            rx.markdown(MarketState.ai_recap),
                            rx.center(
                                rx.text(
                                    (
                                        "公開モードではAIレポート生成を利用できません。"
                                        if not ai_generation_enabled()
                                        else "上部の「AI Market Recap」ボタンを押して、最新の市況レポートを生成します。"
                                    ),
                                    color="gray",
                                ),
                                height="150px",
                            ),
                        ),
                        width="100%",
                        padding="1.5rem",
                    ),
                    width="100%",
                ),
                flash_summary(),
                width="100%",
                spacing="4",
            ),
        ),
        width="100%",
        max_width="1400px",
        margin="0 auto",
    )
