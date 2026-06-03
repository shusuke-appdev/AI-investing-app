import reflex as rx

from frontend.components.flash_summary import flash_summary
from frontend.state.market_state import MarketState
from frontend.template import template


@template
def index() -> rx.Component:
    """メインダッシュボード画面 (Market Intelligence)"""
    return rx.vstack(
        # ヘッダー部分
        rx.hstack(
            rx.heading("Market Intelligence", size="7"),
            rx.spacer(),
            rx.button(
                rx.icon("sparkles", size=18),
                "レポートを生成",
                on_click=MarketState.generate_ai_recap,
                loading=MarketState.is_generating_recap,
                color_scheme="indigo",
                size="3",
                variant="solid",
            ),
            rx.tooltip(
                rx.icon_button(
                    rx.icon("plus", size=16),
                    on_click=MarketState.toggle_recap_focus,
                    size="3",
                    variant="surface",
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
            width="100%",
            align_items="center",
            margin_bottom="2rem",
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
            rx.center(
                rx.spinner(size="3"),
                rx.text("市場データを取得中...", margin_top="1rem", color="gray"),
                direction="column",
                width="100%",
                height="300px",
            ),
            rx.vstack(
                # アセットクラス別概要
                flash_summary(),
                # AI Recap (Gemini)
                rx.box(
                    rx.heading("AI Market Recap", size="5", margin_bottom="1rem"),
                    rx.card(
                        rx.cond(
                            MarketState.ai_recap != "",
                            rx.markdown(MarketState.ai_recap),
                            rx.center(
                                rx.text(
                                    "上部の「AI Market Recap」ボタンを押して、最新の市況レポートを生成します。",
                                    color="gray",
                                ),
                                height="150px",
                            ),
                        ),
                        width="100%",
                        padding="1.5rem",
                    ),
                    width="100%",
                    margin_top="1rem",
                ),
                width="100%",
                spacing="4",
            ),
        ),
        width="100%",
        max_width="1400px",
        margin="0 auto",
    )
