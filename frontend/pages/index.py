import reflex as rx

from frontend.components.flash_summary import flash_summary, market_monitor
from frontend.components.momentum_display import momentum_monitor_component
from frontend.components.option_analysis import option_analysis_component
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
            # AI Recap ボタン（大きめ）
            rx.button(
                rx.icon("sparkles", size=18),
                "AI Market Recap",
                on_click=MarketState.generate_ai_recap,
                loading=MarketState.is_generating_recap,
                color_scheme="indigo",
                size="3",
                variant="solid",
            ),
            # 更新ボタン
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

                # テーマモメンタム監視
                momentum_monitor_component(),

                # オプション分析
                option_analysis_component(),

                # AI Recap (Gemini)
                rx.box(
                    rx.heading("AI Market Recap", size="5", margin_bottom="1rem"),
                    rx.card(
                        rx.cond(
                            MarketState.ai_recap != "",
                            rx.markdown(MarketState.ai_recap),
                            rx.center(
                                rx.text("上部の「AI Market Recap」ボタンを押して、最新の市況レポートを生成します。", color="gray"),
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
        max_width="1400px",
        margin="0 auto",
    )


