import reflex as rx

from frontend.components.data_provenance import data_status_panel, provenance_panel
from frontend.components.fomo_volatility import fomo_volatility_panel
from frontend.components.fundamental_profile import fundamental_profile_panel
from frontend.components.metric_card import metric_card
from frontend.components.probabilistic_signal import probabilistic_signal_panel
from frontend.components.stock_trade_analysis import stock_trade_analysis_panel
from frontend.components.technical_analysis import technical_analysis
from frontend.components.trend_follow_diagnostics import (
    trend_follow_diagnostics_panel,
)
from frontend.components.ui_primitives import (
    empty_state,
    evaluation_badge,
    loading_state,
    page_header,
)
from frontend.state.market_state import MarketState
from frontend.state.stock_state import StockState
from frontend.template import template
from src.app_mode import ai_generation_enabled


def _option_signal_label(value) -> rx.Var:
    return rx.cond(
        value == "upside_squeeze_candidate",
        "上方向ガンマ候補",
        rx.cond(
            value == "downside_vol_expansion",
            "下方向ボラ警戒",
            rx.cond(
                value == "pinning_resistance",
                "抵抗/Pin",
                rx.cond(value == "pinning", "中立/Pin", "判定不能"),
            ),
        ),
    )


def _option_signal_color(value) -> rx.Var:
    return rx.cond(
        value == "upside_squeeze_candidate",
        "green",
        rx.cond(
            value == "downside_vol_expansion",
            "red",
            rx.cond(value == "pinning_resistance", "orange", "gray"),
        ),
    )


def _stock_summary_tile(title: str, value, detail, color: str) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(title, size="1", color=rx.color("gray", 10), weight="bold"),
            rx.text(
                value,
                size="5",
                weight="bold",
                font_variant_numeric="tabular-nums",
            ),
            rx.text(detail, size="1", color=rx.color("gray", 10)),
            spacing="1",
            align_items="start",
            width="100%",
        ),
        border_left=f"4px solid {rx.color(color, 8)}",
        width="100%",
    )


def _stock_decision_summary() -> rx.Component:
    tech = StockState.technical_data
    return rx.grid(
        _stock_summary_tile(
            "テクニカル",
            rx.cond(
                tech.contains("overall_signal_display"),
                tech["overall_signal_display"].to(str)
                + " "
                + tech["overall_score"].to(str)
                + "点",
                "未取得",
            ),
            rx.cond(
                tech.contains("analysis_mode"),
                "分析モード: " + tech["analysis_mode"].to(str),
                "データ取得後に表示します。",
            ),
            "blue",
        ),
        _stock_summary_tile(
            "根拠一致度",
            StockState.purchase_evidence_label
            + " "
            + StockState.purchase_evidence_score_display,
            rx.cond(
                StockState.purchase_evidence_summary != "",
                StockState.purchase_evidence_summary,
                "算出不可の場合は詳細内の欠損理由を確認します。",
            ),
            "green",
        ),
        _stock_summary_tile(
            "適応型ファンダメンタル",
            StockState.fundamental_score_display,
            "充足率 " + StockState.fundamental_coverage_display,
            "cyan",
        ),
        _stock_summary_tile(
            "データ不足",
            rx.cond(
                StockState.data_issue_summary == "主要データは取得済みです。",
                "主要データOK",
                "要確認",
            ),
            StockState.data_issue_summary,
            "amber",
        ),
        columns=rx.breakpoints(initial="1", md="2", xl="4"),
        spacing="3",
        width="100%",
        margin_bottom="1rem",
    )


def _ai_recap_panel() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.heading("AI銘柄要約", size="5", as_="h2", margin_bottom="1rem"),
            rx.spacer(),
            rx.button(
                rx.icon("sparkles", size=16),
                "AI銘柄分析生成",
                on_click=StockState.generate_ai_analysis,
                loading=StockState.is_generating_analysis,
                color_scheme="indigo",
                disabled=not ai_generation_enabled(),
            ),
            width="100%",
            align_items="center",
        ),
        rx.card(
            rx.cond(
                StockState.ai_analysis != "",
                rx.markdown(StockState.ai_analysis),
                rx.center(
                    rx.text(
                        (
                            "公開モードではAI銘柄分析を利用できません。"
                            if not ai_generation_enabled()
                            else "AI銘柄分析レポートを生成して投資判断をサポートします。"
                        ),
                        color="gray",
                    ),
                    height="100px",
                ),
            ),
            width="100%",
            padding="1.5rem",
        ),
        width="100%",
    )


def _news_panel() -> rx.Component:
    return rx.box(
        rx.heading("最新ニュース", size="5", as_="h2", margin_bottom="1rem"),
        rx.cond(
            StockState.news.length() > 0,
            rx.grid(
                rx.foreach(
                    StockState.news,
                    lambda news_item: rx.card(
                        rx.vstack(
                            rx.text(
                                news_item["headline"],
                                weight="bold",
                                margin_bottom="0.5rem",
                            ),
                            rx.text(
                                news_item["summary"],
                                size="2",
                                color="gray",
                                margin_bottom="1rem",
                            ),
                            rx.link(
                                "続きを読む",
                                href=news_item["url"],
                                is_external=True,
                                size="2",
                                color="blue",
                            ),
                            align_items="start",
                        ),
                        width="100%",
                    ),
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                spacing="4",
                width="100%",
            ),
            rx.text("ニュースデータがありません", color="gray"),
        ),
        width="100%",
    )


def _stock_detail_accordion() -> rx.Component:
    return rx.accordion.root(
        rx.accordion.item(
            header="テクニカル / Entry / 確率",
            content=rx.vstack(
                technical_analysis(),
                stock_trade_analysis_panel(),
                probabilistic_signal_panel(),
                width="100%",
                spacing="4",
            ),
        ),
        rx.accordion.item(
            header="FOMO / トレンド堅牢性",
            content=rx.vstack(
                fomo_volatility_panel(),
                trend_follow_diagnostics_panel(),
                width="100%",
                spacing="4",
            ),
        ),
        rx.accordion.item(
            header="AI / ニュース",
            content=rx.vstack(
                _ai_recap_panel(),
                _news_panel(),
                width="100%",
                spacing="4",
            ),
        ),
        rx.accordion.item(
            header="データ状態",
            content=rx.vstack(
                data_status_panel(StockState.data_status),
                provenance_panel(StockState.provenance),
                width="100%",
                spacing="3",
            ),
        ),
        type="multiple",
        default_value=["テクニカル / Entry / 確率"],
        width="100%",
    )


def _ticker_example(ticker: str, label: str) -> rx.Component:
    return rx.button(
        rx.vstack(
            rx.text(ticker, size="2", weight="bold"),
            rx.text(label, size="1"),
            spacing="0",
            align_items="start",
        ),
        on_click=StockState.select_ticker(ticker),
        variant="surface",
        color_scheme="gray",
        min_height="44px",
        aria_label=f"{ticker} {label}の分析を開始",
    )


def _ticker_examples() -> rx.Component:
    us_examples = rx.flex(
        _ticker_example("AAPL", "Apple"),
        _ticker_example("NVDA", "NVIDIA"),
        _ticker_example("MSFT", "Microsoft"),
        _ticker_example("AMZN", "Amazon"),
        _ticker_example("GOOGL", "Alphabet"),
        _ticker_example("META", "Meta"),
        _ticker_example("TSLA", "Tesla"),
        _ticker_example("AMD", "AMD"),
        gap="0.5rem",
        wrap="wrap",
        width="100%",
    )
    jp_examples = rx.flex(
        _ticker_example("7203.T", "トヨタ"),
        _ticker_example("8306.T", "三菱UFJ"),
        _ticker_example("9984.T", "ソフトバンクG"),
        _ticker_example("8035.T", "東京エレクトロン"),
        _ticker_example("6758.T", "ソニーG"),
        gap="0.5rem",
        wrap="wrap",
        width="100%",
    )
    return rx.vstack(
        rx.hstack(
            rx.text("代表ティッカーから開始", size="2", weight="bold"),
            rx.badge("入力例・推奨ではありません", color_scheme="gray"),
            spacing="2",
            wrap="wrap",
        ),
        rx.cond(MarketState.market_type == "JP", jp_examples, us_examples),
        width="100%",
        align_items="start",
        spacing="2",
    )


def _stock_status_item(item) -> rx.Component:
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
        spacing="2",
        align_items="center",
        wrap="wrap",
    )


def _stock_status_summary() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text("更新時刻・利用可能性", size="2", weight="bold"),
            rx.cond(
                StockState.data_status.length() > 0,
                rx.flex(
                    rx.foreach(StockState.data_status, _stock_status_item),
                    gap="0.75rem",
                    wrap="wrap",
                    width="100%",
                ),
                rx.text("データ状態は未取得です。", size="2", color="gray"),
            ),
            rx.text(
                "研究用途の分析です。欠損・部分取得・取得不能は推測で補完しません。",
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


@template
def stock_page() -> rx.Component:
    """個別銘柄分析画面 (Stock)"""
    return rx.vstack(
        page_header(
            "個別銘柄分析",
            "企業概要、株価、テクニカル、モデル出力とデータ制約をまとめて確認します。",
        ),
        # ティッカー入力と取得ボタン
        rx.card(
            rx.vstack(
                rx.form(
                    rx.flex(
                        rx.el.label(
                            "銘柄コード",
                            html_for="stock-ticker",
                            font_weight="bold",
                        ),
                        rx.input(
                            id="stock-ticker",
                            name="ticker",
                            placeholder="例: AAPL",
                            value=StockState.ticker,
                            on_change=StockState.set_ticker,
                            width=rx.breakpoints(initial="100%", sm="220px"),
                        ),
                        rx.button(
                            rx.icon("search", size=16),
                            "データ取得",
                            type="submit",
                            loading=StockState.is_fetching,
                            color_scheme="blue",
                        ),
                        align="center",
                        direction=rx.breakpoints(initial="column", sm="row"),
                        gap="0.75rem",
                        width="100%",
                    ),
                    on_submit=StockState.submit_stock_search,
                    reset_on_submit=False,
                    width="100%",
                ),
                _ticker_examples(),
                rx.cond(
                    StockState.error_msg != "",
                    rx.callout(
                        StockState.error_msg,
                        icon="triangle_alert",
                        color_scheme="red",
                        role="alert",
                        aria_live="polite",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                width="100%",
                align_items="start",
            ),
            width="100%",
            margin_bottom="2rem",
        ),
        rx.cond(
            StockState.profile_warning != "",
            rx.callout(
                StockState.profile_warning,
                icon="info",
                color_scheme="amber",
                margin_bottom="1rem",
                width="100%",
            ),
        ),
        # ローディングスピナー（全体）
        rx.cond(
            StockState.is_fetching,
            loading_state("企業データを取得中..."),
            # データ表示領域
            rx.cond(
                StockState.display_name != "",
                rx.vstack(
                    # 企業名ヘッダ
                    rx.hstack(
                        rx.heading(StockState.display_name, size="6", as_="h2"),
                        rx.cond(
                            StockState.display_exchange != "",
                            rx.badge(
                                StockState.display_exchange,
                                variant="surface",
                            ),
                        ),
                        rx.cond(
                            StockState.display_sector != "",
                            rx.badge(
                                StockState.display_sector,
                                color_scheme="cyan",
                            ),
                        ),
                        align_items="center",
                        width="100%",
                        margin_bottom="1rem",
                    ),
                    _stock_status_summary(),
                    # 現在の評価
                    rx.cond(
                        StockState.technical_data.contains("overall_signal"),
                        rx.card(
                            rx.vstack(
                                rx.text(
                                    "現在の評価",
                                    size="2",
                                    weight="bold",
                                    color=rx.color("gray", 10),
                                ),
                                rx.hstack(
                                    evaluation_badge(
                                        StockState.technical_data[
                                            "overall_signal_display"
                                        ].to(str),
                                        rx.cond(
                                            StockState.technical_data[
                                                "overall_score"
                                            ].to(int)
                                            >= 60,
                                            "green",
                                            rx.cond(
                                                StockState.technical_data[
                                                    "overall_score"
                                                ].to(int)
                                                < 40,
                                                "red",
                                                "yellow",
                                            ),
                                        ),
                                    ),
                                    rx.text(
                                        StockState.technical_data["overall_score"].to(
                                            str
                                        )
                                        + "点",
                                        size="6",
                                        weight="bold",
                                        font_variant_numeric="tabular-nums",
                                    ),
                                    rx.badge(
                                        "分析モード: "
                                        + StockState.technical_data["analysis_mode"].to(
                                            str
                                        ),
                                        size="2",
                                        color_scheme="purple",
                                        variant="surface",
                                    ),
                                    rx.cond(
                                        StockState.technical_data["entry_signal"].to(
                                            str
                                        )
                                        != "",
                                        rx.badge(
                                            StockState.technical_data[
                                                "entry_signal"
                                            ].to(str),
                                            size="2",
                                            color_scheme="orange",
                                        ),
                                    ),
                                    spacing="3",
                                    align_items="center",
                                    wrap="wrap",
                                ),
                                rx.text(
                                    "テクニカル・確率シグナル・トレンド堅牢性は異なる評価軸です。単独で売買判断に使わず、各説明とデータ品質を確認してください。",
                                    size="2",
                                    color=rx.color("gray", 11),
                                ),
                                width="100%",
                                align_items="start",
                            ),
                            width="100%",
                            margin_bottom="1rem",
                        ),
                    ),
                    _stock_decision_summary(),
                    # メトリックカード（主要指標）
                    rx.grid(
                        metric_card(
                            "時価総額 (Market Cap)",
                            StockState.display_market_cap,
                            "",
                        ),
                        metric_card(
                            "PER (株価収益率)",
                            StockState.display_pe_ratio,
                            "",
                        ),
                        metric_card(
                            "配当利回り",
                            StockState.display_dividend_yield,
                            "",
                        ),
                        columns=rx.breakpoints(initial="1", sm="3"),
                        spacing="4",
                        width="100%",
                        margin_bottom="2rem",
                    ),
                    # 上段: チャート + 企業概要
                    rx.grid(
                        # チャートエリア (左 2/3)
                        rx.card(
                            rx.vstack(
                                rx.heading(
                                    "株価推移 (1年)",
                                    size="4",
                                    as_="h2",
                                    margin_bottom="1rem",
                                ),
                                rx.cond(
                                    StockState.chart_data.length() > 0,
                                    rx.recharts.composed_chart(
                                        rx.recharts.area(
                                            data_key="price",
                                            stroke=rx.color("blue", 9),
                                            fill=rx.color("blue", 4),
                                            y_axis_id="left",
                                        ),
                                        rx.recharts.line(
                                            data_key="ma10",
                                            stroke="#FF8042",
                                            dot=False,
                                            y_axis_id="left",
                                        ),
                                        rx.recharts.line(
                                            data_key="ma20",
                                            stroke="#00C49F",
                                            dot=False,
                                            y_axis_id="left",
                                        ),
                                        rx.recharts.line(
                                            data_key="ma50",
                                            stroke="#FFBB28",
                                            dot=False,
                                            y_axis_id="left",
                                        ),
                                        rx.recharts.line(
                                            data_key="ma200",
                                            stroke="#0088FE",
                                            dot=False,
                                            y_axis_id="left",
                                        ),
                                        rx.recharts.bar(
                                            data_key="volume",
                                            fill=rx.color("gray", 5),
                                            y_axis_id="right",
                                        ),
                                        rx.recharts.x_axis(data_key="name"),
                                        rx.recharts.y_axis(
                                            y_axis_id="left",
                                            domain=["auto", "auto"],
                                            scale="log",
                                            orientation="left",
                                        ),
                                        rx.recharts.y_axis(
                                            y_axis_id="right", orientation="right"
                                        ),
                                        rx.recharts.cartesian_grid(
                                            stroke_dasharray="3 3"
                                        ),
                                        rx.recharts.tooltip(),
                                        rx.recharts.legend(),
                                        data=StockState.chart_data,
                                        height=400,
                                        width="100%",
                                    ),
                                    rx.center(
                                        rx.text(
                                            "チャートデータがありません", color="gray"
                                        ),
                                        height="400px",
                                    ),
                                ),
                            ),
                            width="100%",
                        ),
                        # 企業概要エリア (右 1/3)
                        rx.card(
                            rx.vstack(
                                rx.heading(
                                    "企業概要", size="4", as_="h2", margin_bottom="1rem"
                                ),
                                rx.scroll_area(
                                    rx.text(
                                        StockState.display_summary,
                                        size="2",
                                        line_height="1.6",
                                    ),
                                    type="auto",
                                    height="300px",
                                ),
                                width="100%",
                            ),
                            width="100%",
                        ),
                        grid_template_columns=rx.breakpoints(
                            initial="1fr", lg="2fr 1fr"
                        ),
                        spacing="4",
                        width="100%",
                        margin_bottom="2rem",
                    ),
                    # SMART基準セクション
                    rx.cond(
                        StockState.smart_criteria.S.value != "",
                        rx.card(
                            rx.hstack(
                                rx.heading("SMART基準評価", size="4", as_="h3"),
                                rx.cond(
                                    StockState.smart_criteria.all_met,
                                    evaluation_badge("全条件達成", "green"),
                                    rx.cond(
                                        StockState.smart_criteria.overall_status
                                        == "pending",
                                        evaluation_badge("判定不能あり", "gray"),
                                        evaluation_badge("条件未達", "orange"),
                                    ),
                                ),
                                align_items="center",
                                margin_bottom="1rem",
                            ),
                            rx.vstack(
                                rx.text(
                                    rx.cond(
                                        StockState.smart_criteria.S.status == "met",
                                        "✅ ",
                                        rx.cond(
                                            StockState.smart_criteria.S.status
                                            == "unknown",
                                            "❓ ",
                                            "❌ ",
                                        ),
                                    )
                                    + "S（売上成長）: "
                                    + StockState.smart_criteria.S.desc
                                    + " - "
                                    + StockState.smart_criteria.S.value
                                ),
                                rx.text(
                                    rx.cond(
                                        StockState.smart_criteria.M.status == "met",
                                        "✅ ",
                                        rx.cond(
                                            StockState.smart_criteria.M.status
                                            == "unknown",
                                            "❓ ",
                                            "❌ ",
                                        ),
                                    )
                                    + "M（利益率）: "
                                    + StockState.smart_criteria.M.desc
                                    + " - "
                                    + StockState.smart_criteria.M.value
                                ),
                                rx.text(
                                    rx.cond(
                                        StockState.smart_criteria.A.status == "met",
                                        "✅ ",
                                        rx.cond(
                                            StockState.smart_criteria.A.status
                                            == "unknown",
                                            "❓ ",
                                            "❌ ",
                                        ),
                                    )
                                    + "A（利益成長加速）: "
                                    + StockState.smart_criteria.A.desc
                                    + " - "
                                    + StockState.smart_criteria.A.value
                                ),
                                rx.text(
                                    rx.cond(
                                        StockState.smart_criteria.R.status == "met",
                                        "✅ ",
                                        rx.cond(
                                            StockState.smart_criteria.R.status
                                            == "unknown",
                                            "❓ ",
                                            "❌ ",
                                        ),
                                    )
                                    + "R（自己資本利益率）: "
                                    + StockState.smart_criteria.R.desc
                                    + " - "
                                    + StockState.smart_criteria.R.value
                                ),
                                rx.text(
                                    rx.cond(
                                        StockState.smart_criteria.T.status == "met",
                                        "✅ ",
                                        rx.cond(
                                            StockState.smart_criteria.T.status
                                            == "unknown",
                                            "❓ ",
                                            "❌ ",
                                        ),
                                    )
                                    + "T（市場タイミング）: "
                                    + StockState.smart_criteria.T.desc
                                    + " - "
                                    + StockState.smart_criteria.T.value
                                ),
                            ),
                            width="100%",
                            margin_bottom="2rem",
                        ),
                    ),
                    fundamental_profile_panel(),
                    rx.cond(
                        StockState.sector_theme_rating != "",
                        rx.card(
                            rx.vstack(
                                rx.hstack(
                                    rx.heading(
                                        "セクター/テーマ評価", size="4", as_="h3"
                                    ),
                                    evaluation_badge(
                                        StockState.sector_theme_rating_display,
                                        rx.cond(
                                            StockState.sector_theme_rating == "high",
                                            "green",
                                            rx.cond(
                                                StockState.sector_theme_rating
                                                == "conditional",
                                                "orange",
                                                rx.cond(
                                                    StockState.sector_theme_rating
                                                    == "weak",
                                                    "red",
                                                    "gray",
                                                ),
                                            ),
                                        ),
                                    ),
                                    rx.spacer(),
                                    rx.link(
                                        rx.button(
                                            rx.icon("list-ordered", size=15),
                                            "テーマ比較へ",
                                            variant="surface",
                                            size="2",
                                            aria_label="テーマランキングを開く",
                                        ),
                                        href="/theme",
                                        underline="none",
                                    ),
                                    width="100%",
                                    align_items="center",
                                    wrap="wrap",
                                ),
                                rx.hstack(
                                    rx.badge(
                                        rx.cond(
                                            StockState.sector_theme_fundamental_advantage,
                                            "Fundamental優位",
                                            "Fundamental未確認",
                                        ),
                                        color_scheme=rx.cond(
                                            StockState.sector_theme_fundamental_advantage,
                                            "green",
                                            "gray",
                                        ),
                                    ),
                                    rx.badge(
                                        rx.cond(
                                            StockState.sector_theme_flow_advantage,
                                            "Flow優位",
                                            "Flow未確認",
                                        ),
                                        color_scheme=rx.cond(
                                            StockState.sector_theme_flow_advantage,
                                            "green",
                                            "gray",
                                        ),
                                    ),
                                    rx.text(
                                        "ファンダメンタル "
                                        + StockState.sector_theme_fundamental_score_display
                                        + " / フロー "
                                        + StockState.sector_theme_flow_score_display,
                                        size="2",
                                        color=rx.color("gray", 10),
                                    ),
                                    spacing="2",
                                    wrap="wrap",
                                ),
                                rx.hstack(
                                    rx.cond(
                                        StockState.sector_theme_parent_sector != "",
                                        rx.badge(
                                            "親セクター: "
                                            + StockState.sector_theme_parent_sector,
                                            color_scheme="gray",
                                            variant="surface",
                                        ),
                                        rx.fragment(),
                                    ),
                                    rx.cond(
                                        StockState.sector_theme_proxy_ticker != "",
                                        rx.badge(
                                            "Theme ETF: "
                                            + StockState.sector_theme_proxy_ticker,
                                            color_scheme="cyan",
                                            variant="surface",
                                        ),
                                        rx.fragment(),
                                    ),
                                    rx.cond(
                                        StockState.sector_theme_best_rank != "",
                                        rx.badge(
                                            "Trend "
                                            + StockState.sector_theme_best_rank
                                            + "位 / +"
                                            + StockState.sector_theme_rank_points
                                            + "pt",
                                            color_scheme="blue",
                                            variant="surface",
                                        ),
                                        rx.fragment(),
                                    ),
                                    spacing="2",
                                    wrap="wrap",
                                ),
                                rx.cond(
                                    StockState.sector_theme_ranking_summary != "",
                                    rx.text(
                                        StockState.sector_theme_ranking_summary,
                                        size="2",
                                        color=rx.color("gray", 10),
                                    ),
                                    rx.fragment(),
                                ),
                                rx.cond(
                                    StockState.sector_theme_option_proxy != "",
                                    rx.box(
                                        rx.hstack(
                                            rx.text(
                                                "テーマETFオプション",
                                                weight="bold",
                                                size="2",
                                            ),
                                            rx.badge(
                                                StockState.sector_theme_option_proxy,
                                                color_scheme="cyan",
                                                variant="surface",
                                            ),
                                            rx.badge(
                                                _option_signal_label(
                                                    StockState.sector_theme_option_signal
                                                ),
                                                color_scheme=_option_signal_color(
                                                    StockState.sector_theme_option_signal
                                                ),
                                                variant="surface",
                                            ),
                                            rx.badge(
                                                rx.cond(
                                                    StockState.sector_theme_option_provider_active,
                                                    "MarketData.app active",
                                                    "direct Greeksなし",
                                                ),
                                                color_scheme=rx.cond(
                                                    StockState.sector_theme_option_provider_active,
                                                    "green",
                                                    "gray",
                                                ),
                                                variant="surface",
                                            ),
                                            rx.badge(
                                                "Gamma "
                                                + StockState.sector_theme_option_gamma_coverage,
                                                color_scheme=rx.cond(
                                                    StockState.sector_theme_option_gamma_coverage
                                                    == "100%",
                                                    "green",
                                                    "amber",
                                                ),
                                                variant="surface",
                                            ),
                                            rx.cond(
                                                StockState.sector_theme_option_score
                                                != "",
                                                rx.badge(
                                                    StockState.sector_theme_option_score,
                                                    color_scheme="gray",
                                                ),
                                                rx.fragment(),
                                            ),
                                            spacing="2",
                                            wrap="wrap",
                                            align_items="center",
                                        ),
                                        rx.cond(
                                            StockState.sector_theme_option_fallback_reason
                                            != "",
                                            rx.callout(
                                                StockState.sector_theme_option_fallback_reason,
                                                icon="info",
                                                color_scheme="amber",
                                                width="100%",
                                                margin_top="0.5rem",
                                            ),
                                            rx.fragment(),
                                        ),
                                        rx.cond(
                                            StockState.sector_theme_option_summary
                                            != "",
                                            rx.text(
                                                StockState.sector_theme_option_summary,
                                                size="2",
                                                color=rx.color("gray", 10),
                                                margin_top="0.25rem",
                                            ),
                                            rx.fragment(),
                                        ),
                                        rx.cond(
                                            StockState.sector_theme_option_source != "",
                                            rx.text(
                                                "source: "
                                                + StockState.sector_theme_option_source
                                                + " / quality: "
                                                + StockState.sector_theme_option_data_quality
                                                + " / as_of: "
                                                + StockState.sector_theme_option_data_as_of,
                                                size="1",
                                                color=rx.color("gray", 9),
                                                margin_top="0.25rem",
                                            ),
                                            rx.fragment(),
                                        ),
                                        width="100%",
                                        padding="0.75rem",
                                        border=f"1px solid {rx.color('gray', 4)}",
                                        border_radius="8px",
                                    ),
                                    rx.fragment(),
                                ),
                                rx.text(
                                    StockState.sector_theme_rationale,
                                    size="2",
                                    color=rx.color("gray", 11),
                                ),
                                rx.cond(
                                    StockState.sector_theme_themes.length() > 0,
                                    rx.hstack(
                                        rx.foreach(
                                            StockState.sector_theme_themes,
                                            lambda theme: rx.badge(
                                                theme, variant="surface"
                                            ),
                                        ),
                                        spacing="2",
                                        wrap="wrap",
                                    ),
                                    rx.fragment(),
                                ),
                                width="100%",
                                align_items="start",
                            ),
                            width="100%",
                            margin_bottom="2rem",
                        ),
                    ),
                    _stock_detail_accordion(),
                    width="100%",
                ),
                # 初期状態またはデータなし
                empty_state(
                    "銘柄分析を開始",
                    "銘柄コードを入力し、データ取得を実行してください。",
                    "search",
                ),
            ),
        ),
        width="100%",
        max_width="1200px",
        margin="0 auto",
    )
