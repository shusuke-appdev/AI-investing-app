
import reflex as rx

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
    micro = MarketState.microstructure

    return rx.box(
        rx.heading("総合市場監視", size="5", margin_bottom="1rem"),
        rx.card(
            rx.cond(
                eval_data.contains("status"),
                rx.vstack(
                    # 総合評価ヘッダー
                    rx.hstack(
                        rx.text("総合評価:", weight="bold", size="4"),
                        rx.badge(eval_data["status"].to_string(), size="3"),
                        rx.spacer(),
                        rx.text(eval_data["description"].to_string(), size="2", color=rx.color("gray", 11)),
                        align_items="center",
                        spacing="3",
                        width="100%",
                    ),
                    rx.progress(
                        value=((eval_data["score"].to(float) + 1.0) * 50).to(int),
                        max=100,
                        color_scheme=rx.cond(
                            eval_data["score"].to(float) >= 0.3, "green",
                            rx.cond(eval_data["score"].to(float) <= -0.3, "red", "gray")
                        ),
                        width="100%",
                    ),

                    # シグナル詳細（グループ分け）
                    rx.grid(
                        # 強気シグナル
                        rx.vstack(
                            rx.text("🟢 強気シグナル", weight="bold", size="2", color="#10b981"),
                            rx.cond(
                                MarketState.market_signals.length() > 0,  # type: ignore
                                rx.foreach(
                                    MarketState.market_signals,
                                    lambda sig: rx.cond(
                                        sig.category == "bullish",
                                        render_signal(sig),
                                        rx.fragment(),
                                    )
                                ),
                                rx.text("-", size="2", color="gray"),
                            ),
                            width="100%",
                            spacing="1",
                        ),
                        # 弱気シグナル
                        rx.vstack(
                            rx.text("🔴 弱気シグナル", weight="bold", size="2", color="#ef4444"),
                            rx.cond(
                                MarketState.market_signals.length() > 0,  # type: ignore
                                rx.foreach(
                                    MarketState.market_signals,
                                    lambda sig: rx.cond(
                                        sig.category == "bearish",
                                        render_signal(sig),
                                        rx.fragment(),
                                    )
                                ),
                                rx.text("-", size="2", color="gray"),
                            ),
                            width="100%",
                            spacing="1",
                        ),
                        # 中立シグナル
                        rx.vstack(
                            rx.text("⚪ 中立シグナル", weight="bold", size="2", color="gray"),
                            rx.cond(
                                MarketState.market_signals.length() > 0,  # type: ignore
                                rx.foreach(
                                    MarketState.market_signals,
                                    lambda sig: rx.cond(
                                        sig.category == "neutral",
                                        render_signal(sig),
                                        rx.fragment(),
                                    )
                                ),
                                rx.text("-", size="2", color="gray"),
                            ),
                            width="100%",
                            spacing="1",
                        ),
                        columns=rx.breakpoints(initial="1", md="3"),
                        spacing="4",
                        width="100%",
                        margin_top="1rem",
                    ),

                    # マイクロストラクチャー指標
                    rx.cond(
                        micro.unwind_level != "",
                        rx.box(
                            rx.text("マイクロストラクチャー", weight="bold", size="2", margin_bottom="0.5rem"),
                            rx.grid(
                                _micro_card("VRP", micro.vrp, ""),
                                _micro_card("CTA偏り", micro.cta_extremity, ""),
                                _micro_card("流動性", micro.liquidity_status, ""),
                                _micro_card(
                                    "Unwindリスク",
                                    micro.unwind_level,
                                    "",
                                ),
                                columns=rx.breakpoints(initial="2", md="4"),
                                spacing="2",
                                width="100%",
                            ),
                            width="100%",
                            margin_top="1rem",
                            padding="0.75rem",
                            border=f"1px solid {rx.color('gray', 4)}",
                            border_radius="8px",
                        ),
                        rx.fragment(),
                    ),

                    # 市場監視モジュール (Phase 3)
                    rx.cond(
                        MarketState.market_monitor.distribution_spy.status != "",
                        rx.box(
                            rx.text("市場監視 (Market Monitor)", weight="bold", size="2", margin_bottom="0.5rem"),
                            rx.grid(
                                # Distribution Day
                                rx.card(
                                    rx.vstack(
                                        rx.text("売り抜け日 (Distribution Day)", weight="bold", size="1"),
                                        rx.hstack(
                                            rx.text("SPY: ", MarketState.market_monitor.distribution_spy.count.to_string(), "日", size="2"),
                                            rx.badge(MarketState.market_monitor.distribution_spy.status, color_scheme=rx.cond(MarketState.market_monitor.distribution_spy.level == "red", "red", rx.cond(MarketState.market_monitor.distribution_spy.level == "yellow", "orange", "green"))),
                                            align_items="center"
                                        ),
                                        rx.hstack(
                                            rx.text("NDX: ", MarketState.market_monitor.distribution_ndx.count.to_string(), "日", size="2"),
                                            rx.badge(MarketState.market_monitor.distribution_ndx.status, color_scheme=rx.cond(MarketState.market_monitor.distribution_ndx.level == "red", "red", rx.cond(MarketState.market_monitor.distribution_ndx.level == "yellow", "orange", "green"))),
                                            align_items="center"
                                        ),
                                    ),
                                    padding="0.5rem",
                                ),
                                # Yield Spread
                                rx.card(
                                    rx.vstack(
                                        rx.text("イールドスプレッド", weight="bold", size="1"),
                                        rx.cond(
                                            MarketState.market_monitor.yield_spread.overall_status != "",
                                            rx.vstack(
                                                rx.hstack(
                                                    rx.text("SPY:", size="2"),
                                                    rx.badge(MarketState.market_monitor.yield_spread.spreads.SPY.status, color_scheme=rx.cond(MarketState.market_monitor.yield_spread.spreads.SPY.status.contains("株式優位"), "green", "red")),
                                                ),
                                                rx.hstack(
                                                    rx.text("NDX:", size="2"),
                                                    rx.badge(MarketState.market_monitor.yield_spread.spreads.NDX.status, color_scheme=rx.cond(MarketState.market_monitor.yield_spread.spreads.NDX.status.contains("株式優位"), "green", "red")),
                                                ),
                                                spacing="1"
                                            ),
                                            rx.text("-", size="2")
                                        )
                                    ),
                                    padding="0.5rem",
                                ),
                                # Market Climax
                                rx.card(
                                    rx.vstack(
                                        rx.text("市場天井複合検知", weight="bold", size="1"),
                                        rx.cond(
                                            MarketState.market_monitor.distribution_spy.status != "", # Climax is populated along with distribution
                                            rx.vstack(
                                                rx.cond(
                                                    MarketState.market_monitor.climax.is_climax,
                                                    rx.badge("天井警戒 (Climax Detected)", color_scheme="red"),
                                                    rx.badge("正常", color_scheme="green")
                                                ),
                                                rx.cond(
                                                    MarketState.market_monitor.climax.warnings.length() > 0,
                                                    rx.vstack(
                                                        rx.foreach(
                                                            MarketState.market_monitor.climax.warnings,
                                                            lambda w: rx.text("- " + w.to_string(), size="1", color=rx.color("red", 11))
                                                        ),
                                                        spacing="0",
                                                    )
                                                )
                                            ),
                                            rx.text("-", size="2")
                                        )
                                    ),
                                    padding="0.5rem",
                                ),
                                columns=rx.breakpoints(initial="1", md="3"),
                                spacing="2",
                                width="100%",
                            ),
                            width="100%",
                            margin_top="1rem",
                            padding="0.75rem",
                            border=f"1px solid {rx.color('gray', 4)}",
                            border_radius="8px",
                        ),
                        rx.fragment()
                    ),

                    width="100%",
                    spacing="3",
                ),
                rx.text("市場環境を評価中...", color="gray")
            ),
            width="100%",
            margin_bottom="2rem"
        )
    )


def _micro_card(label: str, value, sub_text: str) -> rx.Component:
    """マイクロストラクチャー指標の個別カード"""
    return rx.card(
        rx.vstack(
            rx.text(label, size="1", color=rx.color("gray", 9), font_weight="600"),
            rx.text(value, size="2", font_weight="700"),
            spacing="1",
            align_items="center",
        ),
        padding="0.5rem",
    )
