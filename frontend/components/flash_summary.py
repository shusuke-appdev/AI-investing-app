import reflex as rx
from typing import Dict, Any
from frontend.state.market_state import MarketState

def market_item(item: dict) -> rx.Component:
    """市場データの1行表示"""
    is_positive = item["change"].to(float) >= 0
    color_scheme = rx.cond(is_positive, "green", "red")
    arrow = rx.cond(is_positive, "↑", "↓")
    
    # abs(change)
    abs_change = rx.cond(is_positive, item["change"].to(float), item["change"].to(float) * -1)
    
    return rx.hstack(
        rx.text(item["name"], weight="medium", color=rx.color("gray", 11)),
        rx.spacer(),
        rx.text(item["price"], weight="bold"),
        rx.badge(
            rx.text(f"{arrow} ", abs_change, "%"), 
            color_scheme=color_scheme, 
            variant="surface"
        ),
        width="100%",
        padding_y="0.5rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
        align_items="center",
    )

def render_signal(sig) -> rx.Component:
    """内部指標シグナルの1行表示"""
    return rx.hstack(
        rx.badge(
            sig.name,
            color_scheme=rx.cond(
                sig.score >= 0.3, "green",
                rx.cond(sig.score <= -0.3, "red", "gray")
            ),
            variant="surface",
            width="140px",
            justify_content="center"
        ),
        rx.text(sig.rationale, size="2", color=rx.color("gray", 11)),
        width="100%",
        align_items="center",
        spacing="2",
        padding_y="0.25rem"
    )

def flash_summary() -> rx.Component:
    """アセットクラス別概要"""
    return rx.box(
        rx.heading("アセットクラス別概要", size="5", margin_bottom="1rem"),
        rx.grid(
            rx.card(
                rx.vstack(
                    rx.text("株式指数・金利", weight="bold", size="4"),
                    rx.divider(),
                    rx.cond(
                        MarketState.indices_data.length() > 0,
                        rx.vstack(
                            rx.foreach(MarketState.indices_data, market_item),
                            width="100%"
                        ),
                        rx.text("データがありません", color="gray")
                    ),
                    width="100%"
                ),
                width="100%",
            ),
            rx.card(
                rx.vstack(
                    rx.text("セクター別指数", weight="bold", size="4"),
                    rx.divider(),
                    rx.cond(
                        MarketState.sectors_data.length() > 0,
                        rx.vstack(
                            rx.foreach(MarketState.sectors_data, market_item),
                            width="100%"
                        ),
                        rx.text("データがありません", color="gray")
                    ),
                    width="100%"
                ),
                width="100%",
            ),
            rx.card(
                rx.vstack(
                    rx.text("商品・FX・暗号資産", weight="bold", size="4"),
                    rx.divider(),
                    rx.cond(
                        MarketState.others_data.length() > 0,
                        rx.vstack(
                            rx.foreach(MarketState.others_data, market_item),
                            width="100%"
                        ),
                        rx.text("データがありません", color="gray")
                    ),
                    width="100%"
                ),
                width="100%",
            ),
            columns="3",
            spacing="4",
            width="100%",
        ),
        width="100%",
        margin_bottom="2rem"
    )

def market_monitor() -> rx.Component:

    """総合市場監視"""
    eval_data = MarketState.evaluation
    
    return rx.box(
        rx.heading("総合市場監視", size="5", margin_bottom="1rem"),
        rx.card(
            rx.vstack(
                rx.cond(
                    eval_data.contains("status"),
                    rx.vstack(
                        rx.hstack(
                            rx.text("総合評価:", weight="bold"),
                            rx.badge(eval_data["status"].to_string(), size="2"),
                        ),
                        rx.text(eval_data["description"].to_string(), size="2", color=rx.color("gray", 11)),
                        rx.progress(
                            value=((eval_data["score"].to(float) + 1.0) * 50).to(int), # -1.0~1.0 -> 0~100
                            max=100,
                            color_scheme=rx.cond(
                                eval_data["score"].to(float) >= 0.3, "green",
                                rx.cond(eval_data["score"].to(float) <= -0.3, "red", "gray")
                            ),
                            width="100%",
                            margin_top="1rem"
                        ),
                        rx.divider(margin_y="1rem"),
                        rx.text("詳細指標:", weight="bold", size="2"),
                        rx.cond(
                            MarketState.market_signals.length() > 0,
                            rx.vstack(
                                rx.foreach(MarketState.market_signals, render_signal),
                                width="100%",
                                spacing="2"
                            ),
                            rx.text("詳細データがありません", size="2", color="gray")
                        ),
                        width="100%",
                        align_items="start"
                    ),
                    rx.text("市場環境を評価中...", color="gray")
                )
            ),
            width="100%",
            margin_bottom="2rem"
        )
    )
