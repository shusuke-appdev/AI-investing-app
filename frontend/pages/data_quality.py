import reflex as rx

from frontend.components.data_provenance import data_status_panel, provenance_panel
from frontend.components.ui_primitives import page_header, section_heading
from frontend.state.data_quality_state import DataQualityState
from frontend.state.market_state import MarketState
from frontend.state.portfolio_state import PortfolioState
from frontend.state.stock_state import StockState
from frontend.template import template


def _provider_label(status) -> rx.Var:
    return rx.cond(
        status == "configured",
        "設定済み",
        rx.cond(
            status == "best_effort",
            "best effort",
            rx.cond(status == "optional_missing", "任意未設定", "未設定"),
        ),
    )


def _provider_color(status) -> rx.Var:
    return rx.cond(
        status == "configured",
        "green",
        rx.cond(
            status == "best_effort",
            "blue",
            rx.cond(status == "optional_missing", "gray", "amber"),
        ),
    )


def _provider_card(item) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(item.name, weight="bold", size="2", flex="1"),
                rx.badge(
                    _provider_label(item.status),
                    color_scheme=_provider_color(item.status),
                    variant="surface",
                ),
                width="100%",
                align_items="center",
            ),
            rx.text(item.detail, size="1", color=rx.color("gray", 10)),
            align_items="start",
            spacing="1",
            width="100%",
        ),
        padding="0.75rem",
    )


def _warning_list(items) -> rx.Component:
    return rx.cond(
        items.length() > 0,
        rx.card(
            rx.vstack(
                rx.foreach(
                    items,
                    lambda item: rx.text(
                        "・" + item, size="2", color=rx.color("amber", 11)
                    ),
                ),
                width="100%",
                align_items="start",
            ),
            width="100%",
        ),
        rx.text("警告はありません。", size="2", color="gray"),
    )


@template
def data_quality_page() -> rx.Component:
    return rx.vstack(
        page_header(
            "データ品質",
            "取得元、失敗理由、proxy・推定・キャッシュ利用状況を必要な時だけ確認します。",
            rx.button(
                rx.icon("refresh-cw", size=16),
                "設定状態を更新",
                on_click=DataQualityState.refresh_provider_statuses,
                variant="surface",
            ),
        ),
        section_heading("Provider設定", "秘密値は表示せず、設定有無だけ確認します。"),
        rx.grid(
            rx.foreach(DataQualityState.provider_statuses, _provider_card),
            columns=rx.breakpoints(initial="1", md="2", xl="3"),
            spacing="3",
            width="100%",
        ),
        section_heading("Market", "Market / 市場監視で最後に取得した状態です。"),
        data_status_panel(MarketState.data_status),
        provenance_panel(MarketState.provenance),
        rx.cond(
            MarketState.option_error_msg != "",
            rx.callout(
                MarketState.option_error_msg,
                icon="triangle-alert",
                color_scheme="amber",
                width="100%",
            ),
            rx.fragment(),
        ),
        section_heading("Stock", "個別銘柄分析で最後に取得した状態です。"),
        data_status_panel(StockState.data_status),
        provenance_panel(StockState.provenance),
        section_heading("Portfolio", "ポートフォリオ分析で最後に作成した来歴です。"),
        _warning_list(PortfolioState.analysis_warnings),
        provenance_panel(PortfolioState.provenance),
        width="100%",
        max_width="1200px",
        margin="0 auto",
        spacing="4",
    )
