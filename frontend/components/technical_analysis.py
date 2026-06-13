import reflex as rx

from frontend.components.ui_primitives import evaluation_badge
from frontend.state.stock_state import StockState


def _render_score_row() -> rx.Component:
    """総合スコアとコア指標の1行表示"""
    tech = StockState.technical_data

    overall_score = tech["overall_score"].to(int)
    # 総合スコアのバッジ表示用
    badge_color = rx.cond(
        overall_score >= 60, "green", rx.cond(overall_score < 40, "red", "amber")
    )
    badge_icon = rx.cond(
        overall_score >= 60, "🟢", rx.cond(overall_score < 40, "🔴", "🟡")
    )

    # RSIアイコン
    rsi_val = tech["rsi"].to(float)
    rsi_icon = rx.cond(rsi_val < 30, "🟢", rx.cond(rsi_val > 70, "🔴", "⚪"))

    return rx.grid(
        rx.vstack(
            rx.text("総合評価", size="1", color="gray", weight="bold"),
            rx.hstack(
                rx.text(badge_icon),
                evaluation_badge(
                    rx.text(
                        tech["overall_signal_display"].to(str),
                        " (",
                        overall_score,
                        "点)",
                    ),
                    badge_color,
                ),
            ),
            spacing="1",
        ),
        rx.vstack(
            rx.text("RSI", size="1", color="gray", weight="bold"),
            rx.text(rsi_icon, " ", rsi_val, weight="medium"),
            spacing="1",
        ),
        rx.vstack(
            rx.text("MACD", size="1", color="gray", weight="bold"),
            rx.text(tech["macd_signal"].to(str), weight="medium"),
            spacing="1",
        ),
        rx.vstack(
            rx.text("トレンド", size="1", color="gray", weight="bold"),
            rx.text(tech["ma_trend"].to(str), weight="medium"),
            spacing="1",
        ),
        rx.vstack(
            rx.text("逆張り", size="1", color="gray", weight="bold"),
            rx.cond(
                tech["contrarian_signal"].to(str) == "買い検討ゾーン",
                rx.text("🎯 買いゾーン内", weight="bold", color=rx.color("green", 11)),
                rx.text("📍 ", tech["contrarian_signal"].to(str), weight="medium"),
            ),
            spacing="1",
        ),
        columns="5",
        spacing="4",
        width="100%",
        padding="1rem",
        bg=rx.color("gray", 2),
        border_radius="md",
        margin_bottom="1rem",
    )


def _render_detail_section() -> rx.Component:
    """詳細指標の展開表示"""
    tech = StockState.technical_data

    return rx.accordion.root(
        rx.accordion.item(
            header="詳細指標を見る",
            content=rx.vstack(
                rx.text("基本指標", weight="bold", size="3", margin_bottom="0.5rem"),
                rx.grid(
                    rx.vstack(
                        rx.text(
                            "MA乖離: ", tech["ma_deviation"].to(float), "%", size="2"
                        ),
                        rx.text("BB: ", tech["bb_position"].to(str), size="2"),
                        align_items="start",
                    ),
                    rx.vstack(
                        rx.text(
                            "ATR: $",
                            tech["atr"].to(float),
                            " (",
                            tech["atr_percent"].to(float),
                            "%)",
                            size="2",
                        ),
                        rx.text("BB幅: ", tech["bb_width"].to(float), "%", size="2"),
                        align_items="start",
                    ),
                    rx.vstack(
                        rx.text(
                            "サポート: $", tech["support_price"].to(float), size="2"
                        ),
                        rx.text(
                            "レジスタンス: $",
                            tech["resistance_price"].to(float),
                            size="2",
                        ),
                        align_items="start",
                    ),
                    columns="3",
                    spacing="4",
                    width="100%",
                    margin_bottom="1rem",
                ),
                rx.divider(),
                rx.text(
                    "高度指標",
                    weight="bold",
                    size="3",
                    margin_top="1rem",
                    margin_bottom="0.5rem",
                ),
                rx.grid(
                    rx.vstack(
                        rx.text("一目: ", tech["ichimoku_signal"].to(str), size="2"),
                        align_items="start",
                    ),
                    rx.vstack(
                        rx.text(
                            "動的RSI: ",
                            tech["rsi_dynamic_signal"].to(str),
                            size="2",
                        ),
                        align_items="start",
                    ),
                    rx.vstack(
                        rx.text(
                            "BBスクイズ: ",
                            tech["bb_squeeze_signal"].to(str),
                            size="2",
                        ),
                        align_items="start",
                    ),
                    columns="3",
                    spacing="4",
                    width="100%",
                ),
                width="100%",
                align_items="start",
            ),
        ),
        type="single",
        collapsible=True,
        width="100%",
    )


def technical_analysis() -> rx.Component:
    """テクニカル分析セクション"""
    return rx.cond(
        StockState.technical_data.contains("overall_score"),
        rx.box(
            rx.heading(
                "テクニカル分析", size="5", margin_bottom="1rem", margin_top="2rem"
            ),
            _render_score_row(),
            _render_detail_section(),
            width="100%",
        ),
        rx.box(),
    )
