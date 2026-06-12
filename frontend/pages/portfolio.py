import reflex as rx

from frontend.components.data_provenance import provenance_panel
from frontend.components.ui_primitives import empty_state, page_header, section_heading
from frontend.state.portfolio_state import HoldingItem, PortfolioState
from frontend.template import template


def _render_holding_row(holding: HoldingItem) -> rx.Component:
    """保有銘柄の1行を描画する"""
    return rx.hstack(
        rx.text(holding.ticker, weight="bold", size="3", min_width="80px"),
        rx.text(holding.shares, " 株", size="2", color=rx.color("gray", 11)),
        rx.cond(
            holding.avg_cost,
            rx.text("@ $", holding.avg_cost, size="2", color=rx.color("gray", 9)),
            rx.text("", size="2"),
        ),
        rx.spacer(),
        rx.icon_button(
            rx.icon("trash-2", size=14),
            on_click=PortfolioState.remove_holding(holding.ticker),
            variant="ghost",
            color_scheme="red",
            size="1",
            aria_label=holding.ticker + "を削除",
        ),
        align_items="center",
        width="100%",
        padding="0.75rem 1rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
        _hover={"bg": rx.color("gray", 2)},
    )


def _render_input_section() -> rx.Component:
    """ポートフォリオ管理画面（銘柄追加・削除・保存）"""
    return rx.vstack(
        # ポートフォリオ選択
        rx.hstack(
            rx.heading(PortfolioState.current_portfolio_name, size="5"),
            rx.spacer(),
            rx.button(
                rx.icon("plus", size=15),
                "新規",
                on_click=PortfolioState.new_portfolio,
                variant="outline",
                size="2",
            ),
            rx.cond(
                PortfolioState.current_portfolio_name != "新規ポートフォリオ",
                rx.button(
                    rx.icon("trash-2", size=15),
                    "削除",
                    on_click=PortfolioState.delete_current_portfolio,
                    color_scheme="red",
                    variant="outline",
                    size="2",
                ),
            ),
            width="100%",
            align_items="center",
            margin_bottom="1rem",
        ),
        # 保存済みポートフォリオ一覧
        rx.cond(
            PortfolioState.portfolio_names.length() > 0,
            rx.hstack(
                rx.foreach(
                    PortfolioState.portfolio_names,
                    lambda name: rx.button(
                        name,
                        on_click=PortfolioState.select_portfolio(name),
                        variant=rx.cond(
                            name == PortfolioState.current_portfolio_name,
                            "solid",
                            "outline",
                        ),
                        color_scheme=rx.cond(
                            name == PortfolioState.current_portfolio_name,
                            "blue",
                            "gray",
                        ),
                        size="1",
                    ),
                ),
                flex_wrap="wrap",
                spacing="2",
                margin_bottom="1rem",
                width="100%",
            ),
        ),
        rx.divider(),
        # 銘柄追加フォーム
        rx.card(
            rx.vstack(
                rx.text("銘柄を追加", weight="bold", size="3"),
                rx.hstack(
                    rx.input(
                        placeholder="ティッカー (例: AAPL)",
                        value=PortfolioState.new_ticker,
                        on_change=PortfolioState.set_new_ticker,
                        width=rx.breakpoints(initial="100%", sm="150px"),
                    ),
                    rx.input(
                        placeholder="株数",
                        value=PortfolioState.new_shares,
                        on_change=PortfolioState.set_new_shares,
                        width=rx.breakpoints(initial="100%", sm="120px"),
                        type="number",
                    ),
                    rx.input(
                        placeholder="取得単価 (任意)",
                        value=PortfolioState.new_cost,
                        on_change=PortfolioState.set_new_cost,
                        width=rx.breakpoints(initial="100%", sm="150px"),
                        type="number",
                    ),
                    rx.button(
                        "追加",
                        on_click=PortfolioState.add_holding,
                        color_scheme="blue",
                    ),
                    align_items="center",
                    flex_wrap="wrap",
                    spacing="2",
                ),
                width="100%",
            ),
            width="100%",
            margin_top="1rem",
            margin_bottom="1rem",
        ),
        # 保有銘柄リスト
        rx.cond(
            PortfolioState.holdings.length() > 0,
            rx.vstack(
                rx.text(
                    "保有銘柄 (",
                    PortfolioState.holdings.length(),
                    " 銘柄)",
                    weight="bold",
                    size="3",
                    margin_bottom="0.5rem",
                ),
                rx.card(
                    rx.vstack(
                        rx.foreach(PortfolioState.holdings, _render_holding_row),
                        width="100%",
                        spacing="0",
                    ),
                    width="100%",
                    padding="0",
                ),
                # 保存ボタン
                rx.hstack(
                    rx.input(
                        placeholder="ポートフォリオ名",
                        value=PortfolioState.save_name,
                        on_change=PortfolioState.set_save_name,
                        width="250px",
                    ),
                    rx.button(
                        rx.icon("save", size=15),
                        "保存",
                        on_click=PortfolioState.save_portfolio,
                        loading=PortfolioState.is_loading,
                        color_scheme="green",
                    ),
                    rx.button(
                        rx.icon("chart-no-axes-combined", size=15),
                        "分析する",
                        on_click=PortfolioState.run_analysis,
                        loading=PortfolioState.is_analyzing,
                        color_scheme="blue",
                    ),
                    spacing="2",
                    margin_top="1rem",
                    flex_wrap="wrap",
                ),
                width="100%",
            ),
            empty_state(
                "保有銘柄がありません",
                "銘柄コード、株数、必要に応じて取得単価を入力してください。",
                "briefcase-business",
            ),
        ),
        width="100%",
    )


def _render_analysis_section() -> rx.Component:
    """分析結果の表示"""
    result = PortfolioState.analysis_result
    return rx.vstack(
        section_heading(
            "ポートフォリオ分析",
            "価格を取得できた銘柄だけで時価と構成比を計算します。",
            rx.button(
                rx.icon("arrow-left", size=15),
                "管理画面に戻る",
                on_click=PortfolioState.set_submode("input"),
                variant="outline",
                size="2",
            ),
        ),
        rx.cond(
            PortfolioState.analysis_warnings.length() > 0,
            rx.callout(
                rx.vstack(
                    rx.foreach(
                        PortfolioState.analysis_warnings,
                        lambda item: rx.text(item, size="2"),
                    ),
                    align_items="start",
                    spacing="1",
                ),
                icon="triangle-alert",
                color_scheme="amber",
                width="100%",
            ),
        ),
        provenance_panel(PortfolioState.provenance),
        # サマリーカード
        rx.cond(
            result.contains("total_value"),
            rx.grid(
                rx.card(
                    rx.vstack(
                        rx.text("総資産", size="2", color="gray"),
                        rx.heading(
                            "$",
                            result["total_value"].to(float),
                            size="5",
                            weight="bold",
                        ),
                    ),
                    width="100%",
                ),
                rx.card(
                    rx.vstack(
                        rx.text("銘柄数", size="2", color="gray"),
                        rx.heading(
                            result["num_holdings"].to(int),
                            size="5",
                            weight="bold",
                        ),
                    ),
                    width="100%",
                ),
                columns="2",
                spacing="4",
                width="100%",
                margin_bottom="2rem",
            ),
        ),
        # AIアドバイスセクション
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.heading("AIアドバイス", size="4"),
                    rx.spacer(),
                    rx.button(
                        rx.icon("sparkles", size=15),
                        "AIアドバイスを生成",
                        on_click=PortfolioState.generate_advice,
                        loading=PortfolioState.is_generating_advice,
                        color_scheme="indigo",
                    ),
                    width="100%",
                    align_items="center",
                ),
                rx.cond(
                    PortfolioState.ai_advice != "",
                    rx.markdown(PortfolioState.ai_advice),
                    rx.text(
                        "「AIアドバイスを生成」ボタンを押すと、Geminiがポートフォリオの改善提案を行います。",
                        color="gray",
                        size="2",
                    ),
                ),
                width="100%",
            ),
            width="100%",
            padding="1.5rem",
        ),
        width="100%",
    )


@template
def portfolio_page() -> rx.Component:
    """ポートフォリオ管理ページ"""
    return rx.vstack(
        page_header(
            "ポートフォリオアドバイザー",
            "保有銘柄を管理し、取得可能な価格と分析結果を基に構成を確認します。",
        ),
        # 成功メッセージ
        rx.cond(
            PortfolioState.success_msg != "",
            rx.callout(
                PortfolioState.success_msg,
                icon="check",
                color_scheme="green",
                margin_bottom="1rem",
                width="100%",
            ),
        ),
        # エラーメッセージ
        rx.cond(
            PortfolioState.error_msg != "",
            rx.callout(
                PortfolioState.error_msg,
                icon="triangle_alert",
                color_scheme="red",
                margin_bottom="1rem",
                width="100%",
            ),
        ),
        # サブモード切替
        rx.cond(
            PortfolioState.submode == "input",
            _render_input_section(),
            _render_analysis_section(),
        ),
        width="100%",
        max_width="1000px",
        margin="0 auto",
    )
