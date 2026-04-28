import reflex as rx
from frontend.state.market_state import MarketState
from frontend.components.flash_summary import flash_summary, market_monitor
from frontend.template import template

@template
def index() -> rx.Component:
    """メインダッシュボード画面 (Market Intelligence)"""
    return rx.vstack(
        # ヘッダー部分
        rx.hstack(
            rx.heading("Market Intelligence", size="7"),
            rx.spacer(),
            # 市場切り替えセレクトボックス
            rx.select(
                ["US", "JP"],
                value=MarketState.market_type,
                on_change=MarketState.set_market_type,
                size="2",
                width="120px",
            ),
            rx.button(
                rx.icon("refresh-cw", size=16),
                "更新",
                on_click=MarketState.fetch_market_data,
                loading=MarketState.is_fetching,
                variant="surface",
            ),
            width="100%",
            align_items="center",
            margin_bottom="2rem",
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
            )
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
                # 総合市場監視
                market_monitor(),
                
                # アセットクラス別概要
                flash_summary(),
                
                # AI Recap (Gemini)
                rx.box(
                    rx.hstack(
                        rx.heading("AI Market Recap", size="5", margin_bottom="1rem"),
                        rx.spacer(),
                        rx.button(
                            "✨ AI分析生成",
                            on_click=MarketState.generate_ai_recap,
                            loading=MarketState.is_generating_recap,
                            color_scheme="indigo",
                        ),
                        width="100%",
                        align_items="center",
                    ),
                    rx.card(
                        rx.cond(
                            MarketState.ai_recap != "",
                            rx.markdown(MarketState.ai_recap),
                            rx.center(
                                rx.text("AI分析レポートを生成して最新の市況を要約します。", color="gray"),
                                height="150px"
                            )
                        ),
                        width="100%",
                        padding="1.5rem"
                    ),
                    width="100%",
                    margin_top="1rem"
                ),
                
                width="100%",
                spacing="4"
            )
        ),
        width="100%",
        max_width="1200px",
        margin="0 auto",
    )


