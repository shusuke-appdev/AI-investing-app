from typing import Any

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


def _stage_condition_row(item: dict) -> rx.Component:
    return rx.hstack(
        evaluation_badge(
            rx.cond(item["status"] == "pass", "達成", "未達"),
            rx.cond(item["status"] == "pass", "green", "red"),
        ),
        rx.vstack(
            rx.text(item["label"], size="2", weight="bold"),
            rx.text(item["value"], size="1", color=rx.color("gray", 10)),
            rx.text(item["rationale"], size="1", color=rx.color("gray", 10)),
            align_items="start",
            spacing="1",
        ),
        align_items="start",
        width="100%",
        padding_y="0.35rem",
        border_bottom=f"1px solid {rx.color('gray', 4)}",
    )


def _stage_metric(label: str, value, suffix: str = "") -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color=rx.color("gray", 10)),
        rx.text(value, suffix, size="3", weight="bold"),
        align_items="start",
        spacing="1",
    )


def _render_minervini_section() -> rx.Component:
    tech = StockState.technical_data
    stage = tech["stage_data"].to(dict[str, Any])
    vcp = tech["vcp_data"].to(dict[str, Any])
    conditions = stage["conditions"].to(list[dict])
    warnings = stage["warnings"].to(list[str])
    stage_no = stage["stage"].to(int)
    return rx.cond(
        tech.contains("stage_data"),
        rx.box(
            rx.hstack(
                rx.vstack(
                    rx.heading("ミネルヴィニ ステージ分析", size="4"),
                    rx.text(
                        stage["description"].to(str),
                        size="2",
                        color=rx.color("gray", 11),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.spacer(),
                evaluation_badge(
                    stage["label"].to(str),
                    rx.cond(
                        stage_no == 2,
                        "green",
                        rx.cond(
                            stage_no == 4,
                            "red",
                            rx.cond(stage_no == 0, "gray", "orange"),
                        ),
                    ),
                ),
                rx.badge(
                    stage["stage2_pass_count"].to(str)
                    + "/"
                    + stage["stage2_total_count"].to(str),
                    color_scheme="blue",
                    variant="surface",
                ),
                width="100%",
                align_items="center",
                wrap="wrap",
                margin_bottom="1rem",
            ),
            rx.grid(
                _stage_metric("現在値", stage["current_price"].to(float)),
                _stage_metric("50日線", stage["ma50"].to(float)),
                _stage_metric("150日線", stage["ma150"].to(float)),
                _stage_metric("200日線", stage["ma200"].to(float)),
                _stage_metric(
                    "200日線傾き", stage["ma200_slope_20d_pct"].to(float), "%"
                ),
                _stage_metric("52週安値比", stage["pct_above_low_52w"].to(float), "%"),
                _stage_metric("52週高値比", stage["pct_below_high_52w"].to(float), "%"),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="3",
                width="100%",
                margin_bottom="1rem",
            ),
            rx.cond(
                vcp["is_vcp"].to(bool),
                rx.callout(
                    rx.hstack(
                        rx.badge("VCP", color_scheme="green"),
                        rx.text(
                            "ブレイク水準 ",
                            vcp["breakout_price"].to(float),
                            " / 収縮 ",
                            vcp["contractions"].to(str),
                            "回",
                        ),
                        spacing="2",
                        wrap="wrap",
                    ),
                    icon="chart-no-axes-combined",
                    color_scheme="green",
                    width="100%",
                    margin_bottom="1rem",
                ),
                rx.fragment(),
            ),
            rx.grid(
                rx.foreach(conditions, _stage_condition_row),
                columns=rx.breakpoints(initial="1", md="2"),
                spacing="3",
                width="100%",
            ),
            rx.cond(
                warnings.length() > 0,
                rx.callout(
                    rx.vstack(
                        rx.foreach(
                            warnings,
                            lambda item: rx.text(item, size="2"),
                        ),
                        align_items="start",
                    ),
                    icon="triangle_alert",
                    color_scheme="amber",
                    width="100%",
                    margin_top="1rem",
                ),
                rx.fragment(),
            ),
            width="100%",
            padding="1rem",
            bg=rx.color("gray", 2),
            border=f"1px solid {rx.color('gray', 4)}",
            border_radius="8px",
            margin_bottom="1rem",
        ),
        rx.fragment(),
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
            _render_minervini_section(),
            _render_detail_section(),
            width="100%",
        ),
        rx.box(),
    )
