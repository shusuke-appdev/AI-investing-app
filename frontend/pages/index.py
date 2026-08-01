import reflex as rx

from frontend.components.data_provenance import DataStatusDisplay
from frontend.components.flash_summary import flash_summary
from frontend.components.ui_primitives import page_header, section_heading
from frontend.state.market_state import MarketState
from frontend.template import template


def _status_chip(item: DataStatusDisplay) -> rx.Component:
    return rx.hstack(
        rx.text(item.name, size="1", weight="bold"),
        rx.badge(
            item.status_label,
            color_scheme=rx.cond(
                item.status_key == "ok",
                "green",
                rx.cond(item.status_key == "failed", "red", "amber"),
            ),
            variant="surface",
        ),
        rx.text(
            rx.cond(item.fetched_at != "", item.fetched_at, "更新時刻不明"),
            size="1",
            color=rx.color("gray", 10),
        ),
        padding="0.45rem 0.65rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="0.5rem",
        align_items="center",
        min_height="40px",
    )


def _market_status_strip() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("clock-3", size=18, color=rx.color("blue", 9)),
                rx.text("更新時刻・利用可能性", weight="bold", size="2"),
                width="100%",
                align_items="center",
            ),
            rx.cond(
                MarketState.data_status.length() > 0,
                rx.flex(
                    rx.foreach(MarketState.data_status, _status_chip),
                    gap="0.5rem",
                    wrap="wrap",
                    width="100%",
                ),
                rx.text(
                    "市場データは未取得です。概要更新後に時刻と状態を表示します。",
                    size="2",
                    color=rx.color("gray", 10),
                ),
            ),
            rx.text(
                "研究用途の情報です。欠損・部分取得・取得不能は正常値に置き換えず、そのまま表示します。",
                size="1",
                color=rx.color("gray", 10),
            ),
            width="100%",
            align_items="start",
            spacing="2",
        ),
        width="100%",
        variant="surface",
    )


def _ai_recap_section() -> rx.Component:
    return rx.box(
        section_heading(
            "AI Market Recap",
            "表示済みの市場コンテキストを再利用して市況を整理します。",
        ),
        rx.cond(
            MarketState.ai_recap_notice_msg != "",
            rx.callout(
                MarketState.ai_recap_notice_msg,
                icon="info",
                color_scheme="amber",
                width="100%",
                margin_bottom="0.75rem",
            ),
        ),
        rx.card(
            rx.cond(
                MarketState.ai_recap != "",
                rx.markdown(MarketState.ai_recap),
                rx.text(
                    "上部の「レポートを生成」を押すと、表示済みデータから市況を整理します。",
                    color=rx.color("gray", 10),
                    size="2",
                ),
            ),
            width="100%",
            padding="1rem",
        ),
        width="100%",
    )


@template
def index() -> rx.Component:
    """メインダッシュボード画面 (Market Intelligence)"""
    return rx.vstack(
        page_header(
            "今日の市場",
            "主要資産の変化とAI要約を、前回データを保ったまま確認します。",
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
                    aria_label="任意の分析項目を追加",
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
        rx.cond(
            MarketState.is_fetching,
            rx.callout(
                "最新データを取得中です。完了まで前回の表示を維持します。",
                icon="refresh-cw",
                color_scheme="blue",
                width="100%",
            ),
        ),
        flash_summary(),
        _ai_recap_section(),
        _market_status_strip(),
        width="100%",
        max_width="1400px",
        margin="0 auto",
    )
