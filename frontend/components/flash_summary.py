import reflex as rx

from frontend.state.market_state import MarketState


def market_item(item: dict) -> rx.Component:
    """Render one market data row."""

    is_positive = item["change"].to(float) >= 0
    color_scheme = rx.cond(is_positive, "green", "red")
    arrow = rx.cond(is_positive, "▲", "▼")
    abs_change = rx.cond(
        is_positive, item["change"].to(float), item["change"].to(float) * -1
    )

    return rx.hstack(
        rx.text(item["name"], weight="medium", color=rx.color("gray", 11)),
        rx.spacer(),
        rx.text(item["price"], weight="bold"),
        rx.badge(
            rx.text(arrow, " ", abs_change, "%"),
            color_scheme=color_scheme,
            variant="surface",
        ),
        width="100%",
        padding_y="0.5rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
        align_items="center",
    )


def render_signal(sig) -> rx.Component:
    """Render one market environment signal."""

    return rx.hstack(
        rx.badge(
            sig.name,
            color_scheme=rx.cond(
                sig.score >= 0.3, "green", rx.cond(sig.score <= -0.3, "red", "gray")
            ),
            variant="surface",
            width="140px",
            justify_content="center",
        ),
        rx.text(sig.rationale, size="2", color=rx.color("gray", 11)),
        width="100%",
        align_items="center",
        spacing="2",
        padding_y="0.25rem",
    )


def flash_summary() -> rx.Component:
    """Render cross-asset market summary."""

    return rx.box(
        rx.heading("アセットクラス別概要", size="5", margin_bottom="1rem"),
        rx.grid(
            _market_group("株式指数・金利", MarketState.indices_data),
            _market_group("セクター別指数", MarketState.sectors_data),
            _market_group("商品・FX・暗号資産", MarketState.others_data),
            columns=rx.breakpoints(initial="1", md="3"),
            spacing="4",
            width="100%",
        ),
        width="100%",
        margin_bottom="2rem",
    )


def _market_group(title: str, rows) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(title, weight="bold", size="4"),
            rx.divider(),
            rx.cond(
                rows.length() > 0,
                rx.vstack(rx.foreach(rows, market_item), width="100%"),
                rx.text("データがありません", color="gray"),
            ),
            width="100%",
        ),
        width="100%",
    )


def market_monitor() -> rx.Component:
    """Render market monitor and advanced technical context."""

    eval_data = MarketState.evaluation
    micro = MarketState.microstructure

    return rx.box(
        rx.heading("総合市場監視", size="5", margin_bottom="1rem"),
        rx.card(
            rx.cond(
                eval_data.contains("status"),
                rx.vstack(
                    _environment_header(eval_data),
                    _signal_grid(),
                    rx.cond(
                        micro.unwind_level != "",
                        _microstructure_panel(micro),
                        rx.fragment(),
                    ),
                    rx.cond(
                        MarketState.market_monitor.distribution_spy.status != "",
                        _market_monitor_panel(),
                        rx.fragment(),
                    ),
                    width="100%",
                    spacing="3",
                ),
                rx.text("市場環境を評価中...", color="gray"),
            ),
            width="100%",
            margin_bottom="2rem",
        ),
    )


def _environment_header(eval_data) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text("総合評価:", weight="bold", size="4"),
            rx.badge(eval_data["status"].to_string(), size="3"),
            rx.spacer(),
            rx.text(
                eval_data["description"].to_string(),
                size="2",
                color=rx.color("gray", 11),
            ),
            align_items="center",
            spacing="3",
            width="100%",
        ),
        rx.progress(
            value=((eval_data["score"].to(float) + 1.0) * 50).to(int),
            max=100,
            color_scheme=rx.cond(
                eval_data["score"].to(float) >= 0.3,
                "green",
                rx.cond(eval_data["score"].to(float) <= -0.3, "red", "gray"),
            ),
            width="100%",
        ),
        width="100%",
        spacing="2",
    )


def _signal_grid() -> rx.Component:
    return rx.grid(
        _signal_column("強気シグナル", "bullish", "green"),
        _signal_column("弱気シグナル", "bearish", "red"),
        _signal_column("中立シグナル", "neutral", "gray"),
        columns=rx.breakpoints(initial="1", md="3"),
        spacing="4",
        width="100%",
        margin_top="1rem",
    )


def _signal_column(title: str, category: str, color: str) -> rx.Component:
    return rx.vstack(
        rx.text(title, weight="bold", size="2", color=rx.color(color, 10)),
        rx.cond(
            MarketState.market_signals.length() > 0,
            rx.foreach(
                MarketState.market_signals,
                lambda sig: rx.cond(
                    sig.category == category, render_signal(sig), rx.fragment()
                ),
            ),
            rx.text("-", size="2", color="gray"),
        ),
        width="100%",
        spacing="1",
    )


def _microstructure_panel(micro) -> rx.Component:
    return rx.box(
        rx.text(
            "マイクロストラクチャー",
            weight="bold",
            size="2",
            margin_bottom="0.5rem",
        ),
        rx.grid(
            _micro_card("VRP", micro.vrp),
            _micro_card("CTA偏り", micro.cta_extremity),
            _micro_card("流動性", micro.liquidity_status),
            _micro_card("Unwindリスク", micro.unwind_level),
            columns=rx.breakpoints(initial="2", md="4"),
            spacing="2",
            width="100%",
        ),
        width="100%",
        margin_top="1rem",
        padding="0.75rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
    )


def _market_monitor_panel() -> rx.Component:
    return rx.box(
        rx.text(
            "市場監視 (Market Monitor)",
            weight="bold",
            size="2",
            margin_bottom="0.5rem",
        ),
        rx.grid(
            _distribution_card(),
            _yield_spread_card(),
            _climax_card(),
            columns=rx.breakpoints(initial="1", md="3"),
            spacing="2",
            width="100%",
        ),
        width="100%",
        margin_top="1rem",
        padding="0.75rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
    )


def _distribution_card() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text("売り抜け日", weight="bold", size="1"),
            _distribution_row(
                "SPY",
                MarketState.market_monitor.distribution_spy.count,
                MarketState.market_monitor.distribution_spy.status,
                MarketState.market_monitor.distribution_spy.level,
            ),
            _distribution_row(
                "NDX",
                MarketState.market_monitor.distribution_ndx.count,
                MarketState.market_monitor.distribution_ndx.status,
                MarketState.market_monitor.distribution_ndx.level,
            ),
            align_items="start",
        ),
        padding="0.5rem",
    )


def _distribution_row(label: str, count, status, level) -> rx.Component:
    return rx.hstack(
        rx.text(label, ": ", count.to_string(), "日", size="2"),
        rx.badge(status, color_scheme=_level_color(level)),
        align_items="center",
    )


def _yield_spread_card() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text("イールドスプレッド", weight="bold", size="1"),
            rx.cond(
                MarketState.market_monitor.yield_spread.overall_status != "",
                rx.vstack(
                    _spread_row(
                        "SPY",
                        MarketState.market_monitor.yield_spread.spreads.SPY.status,
                        MarketState.market_monitor.yield_spread.spreads.SPY.level,
                    ),
                    _spread_row(
                        "NDX",
                        MarketState.market_monitor.yield_spread.spreads.NDX.status,
                        MarketState.market_monitor.yield_spread.spreads.NDX.level,
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.text("-", size="2"),
            ),
            align_items="start",
        ),
        padding="0.5rem",
    )


def _spread_row(label: str, status, level) -> rx.Component:
    return rx.hstack(
        rx.text(label, ":", size="2"),
        rx.badge(status, color_scheme=_level_color(level)),
        align_items="center",
    )


def _climax_card() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text("市場クライマックス検知", weight="bold", size="1"),
            rx.cond(
                MarketState.market_monitor.climax.is_climax,
                rx.badge("警戒", color_scheme="red"),
                rx.badge("正常", color_scheme="green"),
            ),
            rx.cond(
                MarketState.market_monitor.climax.warnings.length() > 0,
                rx.vstack(
                    rx.foreach(
                        MarketState.market_monitor.climax.warnings,
                        lambda w: rx.text(
                            "- " + w.to_string(),
                            size="1",
                            color=rx.color("red", 11),
                        ),
                    ),
                    spacing="0",
                    align_items="start",
                ),
                rx.fragment(),
            ),
            align_items="start",
        ),
        padding="0.5rem",
    )


def _level_color(level) -> rx.Var:
    return rx.cond(
        level == "green",
        "green",
        rx.cond(level == "yellow", "orange", rx.cond(level == "red", "red", "gray")),
    )


def _micro_card(label: str, value) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(label, size="1", color=rx.color("gray", 9), font_weight="600"),
            rx.text(value, size="2", font_weight="700"),
            spacing="1",
            align_items="center",
        ),
        padding="0.5rem",
    )
