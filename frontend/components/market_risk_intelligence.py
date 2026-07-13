import reflex as rx

from frontend.state.market_state import MarketState


def market_risk_intelligence_panel() -> rx.Component:
    """Compact volatility, sentiment, and top-risk summaries."""

    return rx.vstack(
        rx.grid(
            _summary_card(
                "ボラティリティ・レジーム",
                MarketState.volatility_summary,
                MarketState.volatility_posture,
                "activity",
            ),
            _summary_card(
                "独自 Fear & Greed",
                MarketState.sentiment_summary,
                MarketState.sentiment_coverage,
                "gauge",
            ),
            _summary_card(
                "天井警戒サインポスト",
                MarketState.top_risk_summary,
                "BofA-inspired / 非公式",
                "triangle-alert",
            ),
            columns=rx.breakpoints(initial="1", md="3"),
            spacing="3",
            width="100%",
        ),
        _short_forecast_panel(),
        _composite_sentiment_panel(),
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.heading("高ボラ銘柄 FOMOスキャン", size="4", as_="h2"),
                    rx.spacer(),
                    rx.button(
                        "スキャン実行",
                        on_click=MarketState.refresh_fomo_scan,
                        loading=MarketState.is_scanning_fomo,
                        variant="surface",
                    ),
                    width="100%",
                ),
                rx.text(
                    rx.cond(
                        MarketState.fomo_scan_summary != "",
                        MarketState.fomo_scan_summary,
                        "明示実行時のみ対象銘柄を取得します。",
                    ),
                    size="2",
                    color=rx.color("gray", 10),
                ),
                rx.foreach(
                    MarketState.fomo_scan_items,
                    lambda item: rx.hstack(
                        rx.text(item.ticker, weight="bold", width="90px"),
                        rx.badge(item.label, variant="surface"),
                        rx.text(item.risk_level, size="1", color=rx.color("gray", 10)),
                        width="100%",
                    ),
                ),
                align_items="start",
                width="100%",
            ),
            width="100%",
        ),
        width="100%",
    )


def _short_forecast_panel() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("短期予測 1・5・20営業日", size="4", as_="h3"),
                rx.spacer(),
                rx.badge("研究用確率モデル", color_scheme="blue", variant="surface"),
                width="100%",
                align_items="center",
            ),
            rx.text(
                "確率と予測区間はウォークフォワード検証後のみ戦略へ連携します。",
                size="1",
                color=rx.color("gray", 10),
            ),
            rx.grid(
                rx.foreach(MarketState.short_horizon_forecasts, _forecast_row),
                columns=rx.breakpoints(initial="1", md="2", xl="3"),
                spacing="2",
                width="100%",
            ),
            align_items="start",
            width="100%",
        ),
        width="100%",
    )


def _forecast_row(item) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(item.ticker + " / " + item.horizon, weight="bold", size="2"),
                rx.spacer(),
                rx.badge(
                    item.status_label,
                    color_scheme=rx.cond(item.status == "validated", "green", "amber"),
                    variant="surface",
                ),
                width="100%",
            ),
            rx.text("上昇確率 " + item.probability_up, size="3", weight="bold"),
            rx.text("予測区間 " + item.range_text, size="1"),
            rx.hstack(
                rx.badge("方向 " + item.direction_label, variant="outline"),
                rx.badge(
                    "リスク " + item.risk_label,
                    color_scheme=_risk_color(item.risk_level),
                    variant="surface",
                ),
                spacing="2",
                wrap="wrap",
            ),
            rx.text(
                "implied move " + item.implied_move + " / as-of " + item.as_of,
                size="1",
                color=rx.color("gray", 9),
            ),
            align_items="start",
            spacing="1",
        ),
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
        padding="0.65rem",
        width="100%",
    )


def _composite_sentiment_panel() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("複合センチメント判定", size="4", as_="h3"),
                rx.spacer(),
                rx.badge("警戒補正のみ", color_scheme="orange", variant="surface"),
                width="100%",
                align_items="center",
            ),
            rx.text(
                "VIX・SKEW・VVIX・Put/Call・期間構造・gamma・市場参加度を組み合わせます。",
                size="1",
                color=rx.color("gray", 10),
            ),
            rx.grid(
                rx.foreach(MarketState.composite_sentiment_items, _composite_card),
                columns=rx.breakpoints(initial="1", lg="2"),
                spacing="3",
                width="100%",
            ),
            align_items="start",
            width="100%",
        ),
        width="100%",
    )


def _composite_card(item) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(item.ticker, weight="bold"),
                rx.badge(item.state_label, color_scheme="blue", variant="surface"),
                rx.badge(
                    item.status_label,
                    color_scheme=rx.cond(item.status == "confirmed", "green", "amber"),
                    variant="outline",
                ),
                rx.spacer(),
                rx.badge(
                    "警戒下限 " + item.risk_label,
                    color_scheme=_risk_color(item.risk_floor),
                    variant="surface",
                ),
                width="100%",
                wrap="wrap",
            ),
            rx.text(item.summary, size="2"),
            rx.cond(
                item.reversal_watch,
                rx.callout(
                    "反発候補ですが、確率やStock評価の格上げには使用しません。",
                    icon="info",
                    color_scheme="blue",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.foreach(item.evidence, _composite_evidence_row),
            rx.text("as-of " + item.as_of, size="1", color=rx.color("gray", 9)),
            align_items="start",
            spacing="2",
            width="100%",
        ),
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
        padding="0.75rem",
        width="100%",
    )


def _composite_evidence_row(item) -> rx.Component:
    return rx.hstack(
        rx.badge(
            item.status_label,
            color_scheme=rx.cond(
                item.status == "met",
                "green",
                rx.cond(item.status == "not_met", "gray", "amber"),
            ),
            variant="surface",
        ),
        rx.vstack(
            rx.text(item.label + " / " + item.value, size="1", weight="bold"),
            rx.text(
                item.threshold + " / " + item.source,
                size="1",
                color=rx.color("gray", 9),
            ),
            spacing="0",
            align_items="start",
        ),
        align_items="start",
        width="100%",
    )


def _risk_color(value) -> rx.Var:
    return rx.cond(
        value == "extreme",
        "red",
        rx.cond(
            value == "high",
            "orange",
            rx.cond(
                value == "medium", "amber", rx.cond(value == "low", "green", "gray")
            ),
        ),
    )


def _summary_card(title, summary, badge, icon: str) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(icon, size=17),
                rx.text(title, weight="bold", size="2"),
                width="100%",
            ),
            rx.text(
                rx.cond(summary != "", summary, "詳細更新後に表示します。"),
                size="2",
            ),
            rx.cond(
                badge != "",
                rx.badge(badge, variant="surface", color_scheme="blue"),
                rx.fragment(),
            ),
            align_items="start",
            spacing="2",
        ),
        width="100%",
    )
