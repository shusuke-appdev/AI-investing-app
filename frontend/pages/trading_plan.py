import reflex as rx

from frontend.components.ui_primitives import (
    empty_state,
    loading_state,
    page_header,
    private_mode_notice,
)
from frontend.state.trading_plan_state import TradingPlanState
from frontend.template import template
from src.app_mode import personal_data_enabled


def _plan_card(plan: dict) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading(plan["ticker"], size="4"),
                rx.badge(plan["status"]),
                rx.badge("Grade " + plan["grade"].to(str), variant="surface"),
                rx.badge(plan["setup_status"], variant="surface"),
                rx.spacer(),
                rx.text(plan["entry_date"], size="1", color=rx.color("gray", 10)),
                width="100%",
                align_items="center",
                wrap="wrap",
            ),
            rx.grid(
                _metric("Entry", plan["entry_display"]),
                _metric("Shares", plan["shares_display"]),
                _metric("1R / share", plan["one_r_display"]),
                _metric("Planned Loss", plan["composite_loss_display"]),
                _metric("Session", plan["session_stage"]),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="3",
                width="100%",
            ),
            rx.markdown(plan["stops_display"]),
            rx.text(
                "ATR% Extension 利確目安: " + plan["profit_levels_display"].to(str),
                size="2",
                color=rx.color("gray", 10),
            ),
            rx.hstack(
                rx.badge("T+1 " + plan["t1_status"].to(str), variant="surface"),
                rx.badge("T+3 " + plan["t3_status"].to(str), variant="surface"),
                rx.spacer(),
                rx.button(
                    "Active",
                    on_click=TradingPlanState.activate_plan(plan["plan_id"]),
                    size="1",
                    color_scheme="green",
                ),
                rx.button(
                    "T+1確認",
                    on_click=TradingPlanState.mark_t1_confirmed(plan["plan_id"]),
                    size="1",
                    variant="outline",
                ),
                rx.button(
                    "T+3確認",
                    on_click=TradingPlanState.mark_t3_confirmed(plan["plan_id"]),
                    size="1",
                    variant="outline",
                ),
                rx.button(
                    "Close",
                    on_click=TradingPlanState.close_plan(plan["plan_id"]),
                    size="1",
                    variant="outline",
                ),
                rx.button(
                    "メモ追加",
                    on_click=TradingPlanState.add_journal_note(plan["plan_id"]),
                    size="1",
                    variant="outline",
                ),
                rx.icon_button(
                    rx.icon("trash-2", size=14),
                    on_click=TradingPlanState.delete_plan(plan["plan_id"]),
                    size="1",
                    variant="ghost",
                    color_scheme="red",
                    aria_label="Trading Planを削除",
                ),
                width="100%",
                align_items="center",
                wrap="wrap",
                spacing="2",
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
    )


def _metric(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color=rx.color("gray", 10)),
        rx.text(value, weight="bold"),
        align_items="start",
        spacing="1",
    )


def _create_form() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("新規Trading Plan", size="4"),
            rx.text(
                "Stockと同じ日足Entry Frameworkを取得し、Entry時点のスナップショットを保存します。",
                size="2",
                color=rx.color("gray", 10),
            ),
            rx.grid(
                rx.input(
                    placeholder="Ticker (AAPL / 7203.T)",
                    value=TradingPlanState.ticker,
                    on_change=TradingPlanState.set_ticker,
                ),
                rx.input(
                    type="date",
                    value=TradingPlanState.entry_date,
                    on_change=TradingPlanState.set_entry_date,
                ),
                rx.input(
                    placeholder="Entry価格",
                    type="number",
                    value=TradingPlanState.entry_price,
                    on_change=TradingPlanState.set_entry_price,
                ),
                rx.input(
                    placeholder="最終ストップ価格",
                    type="number",
                    value=TradingPlanState.final_stop_price,
                    on_change=TradingPlanState.set_final_stop_price,
                ),
                rx.input(
                    placeholder="口座金額",
                    type="number",
                    value=TradingPlanState.account_value,
                    on_change=TradingPlanState.set_account_value,
                ),
                rx.input(
                    placeholder="許容リスク率 %",
                    type="number",
                    value=TradingPlanState.risk_percent,
                    on_change=TradingPlanState.set_risk_percent,
                ),
                rx.input(
                    placeholder="株数（空欄なら推奨値）",
                    type="number",
                    value=TradingPlanState.shares,
                    on_change=TradingPlanState.set_shares,
                ),
                columns=rx.breakpoints(initial="1", sm="2", lg="4"),
                spacing="3",
                width="100%",
            ),
            rx.grid(
                rx.input(
                    placeholder="Close時の実現R（例: 4.0）",
                    type="number",
                    value=TradingPlanState.realized_r,
                    on_change=TradingPlanState.set_realized_r,
                ),
                rx.input(
                    placeholder="ジャーナルメモ",
                    value=TradingPlanState.journal_note,
                    on_change=TradingPlanState.set_journal_note,
                ),
                rx.input(
                    placeholder="ミスタグ（任意）",
                    value=TradingPlanState.mistake_tag,
                    on_change=TradingPlanState.set_mistake_tag,
                ),
                columns=rx.breakpoints(initial="1", md="3"),
                spacing="3",
                width="100%",
            ),
            rx.button(
                rx.icon("plus", size=16),
                "計画を作成",
                on_click=TradingPlanState.create_plan,
                loading=TradingPlanState.is_loading,
                color_scheme="blue",
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
    )


def _review_panel() -> rx.Component:
    review = TradingPlanState.review
    return rx.cond(
        review.contains("closed_count"),
        rx.card(
            rx.vstack(
                rx.heading("Process Review", size="4"),
                rx.grid(
                    _metric("Closed", review["closed_count"].to(str)),
                    _metric("Win Rate", review["win_rate"].to(str) + "%"),
                    _metric("Avg Win", review["avg_win_r"].to(str) + "R"),
                    _metric("Avg Loss", review["avg_loss_r"].to(str) + "R"),
                    _metric("Expectancy", review["expectancy_r"].to(str) + "R"),
                    _metric(
                        "Losses Absorbed",
                        review["losses_absorbed"].to(str),
                    ),
                    _metric(
                        "Rule Adherence",
                        review["rule_adherence"].to(str) + "%",
                    ),
                    columns=rx.breakpoints(initial="2", md="4"),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
                align_items="start",
            ),
            width="100%",
        ),
        rx.fragment(),
    )


@template
def trading_plan_page() -> rx.Component:
    if not personal_data_enabled():
        return private_mode_notice("Trading Plan")

    return rx.vstack(
        page_header(
            "Trading Plan",
            "Trade Tight, Think in R, Focus on Process。Entry分析と資産集計から独立した実行管理です。",
        ),
        rx.cond(
            TradingPlanState.error_msg != "",
            rx.callout(
                TradingPlanState.error_msg,
                icon="triangle-alert",
                color_scheme="red",
                width="100%",
            ),
        ),
        rx.cond(
            TradingPlanState.success_msg != "",
            rx.callout(
                TradingPlanState.success_msg,
                icon="check",
                color_scheme="green",
                width="100%",
            ),
        ),
        _create_form(),
        _review_panel(),
        rx.hstack(
            rx.text(
                "価格取得はこの操作時のみ実行し、銘柄ごとに1回へ集約します。",
                size="2",
                color=rx.color("gray", 10),
            ),
            rx.spacer(),
            rx.button(
                rx.icon("refresh-cw", size=16),
                "T+1/T+3候補を更新",
                on_click=TradingPlanState.refresh_checkpoint_candidates,
                loading=TradingPlanState.is_loading,
                variant="outline",
            ),
            width="100%",
            align_items="center",
            wrap="wrap",
        ),
        rx.cond(
            TradingPlanState.is_loading & (TradingPlanState.plans.length() == 0),
            loading_state("Trading Planを取得中..."),
            rx.cond(
                TradingPlanState.plans.length() > 0,
                rx.vstack(
                    rx.foreach(TradingPlanState.plans, _plan_card),
                    width="100%",
                    spacing="3",
                ),
                empty_state(
                    "Trading Planがありません",
                    "候補銘柄のEntry価格と最終ストップを入力して、R基準の計画を作成してください。",
                    "clipboard-list",
                ),
            ),
        ),
        width="100%",
        max_width="1200px",
        margin="0 auto",
        spacing="4",
    )
