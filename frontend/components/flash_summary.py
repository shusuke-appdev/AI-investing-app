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
                    _ibd_regime_panel(),
                    _playbook_panel(),
                    rx.cond(
                        (MarketState.strategy_regime.label != "")
                        | (MarketState.important_levels.length() > 0),
                        _strategy_regime_panel(),
                        rx.fragment(),
                    ),
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
                    rx.cond(
                        MarketState.credit_stress.status != "",
                        _credit_and_flow_panel(),
                        rx.fragment(),
                    ),
                    rx.cond(
                        MarketState.sector_flow_groups.length() > 0,
                        _sector_flow_panel(),
                        rx.fragment(),
                    ),
                    rx.cond(
                        MarketState.japan_conditions.length() > 0,
                        _nikkei_conditions_panel(),
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


def watch_indices_strip() -> rx.Component:
    """Render closing-price movement for S&P 500 and Nasdaq 100."""

    return rx.box(
        rx.heading("主要指数 終値ベース", size="5", margin_bottom="1rem"),
        rx.grid(
            rx.foreach(MarketState.watch_indices_data, market_item),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def market_distortion_panel() -> rx.Component:
    """Render fundamental-vs-flow distortion candidates."""

    return rx.box(
        rx.heading("市場の歪み検知", size="5", margin_bottom="0.75rem"),
        rx.text(
            "ファンダメンタルと資金フローの乖離を検出",
            size="2",
            color=rx.color("gray", 10),
            margin_bottom="1rem",
        ),
        rx.grid(
            _distortion_column(
                "強気歪み Top 5", MarketState.bullish_distortions, "green"
            ),
            _distortion_column(
                "弱気歪み Top 5", MarketState.bearish_distortions, "red"
            ),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="4",
            width="100%",
        ),
        width="100%",
    )


def trend_ranking_panel() -> rx.Component:
    """Render the integrated trend ranking and opportunity themes."""

    return rx.box(
        rx.heading("統合トレンドランキング", size="5", margin_bottom="0.75rem"),
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.text(
                        MarketState.trend_ranking_summary,
                        size="2",
                        color=rx.color("gray", 11),
                        flex="1",
                    ),
                    rx.badge("Options best effort", color_scheme="blue"),
                    width="100%",
                    align_items="center",
                ),
                rx.cond(
                    MarketState.opportunity_theme_items.length() > 0,
                    rx.box(
                        rx.text("注目セクター/テーマ", weight="bold", size="2"),
                        rx.grid(
                            rx.foreach(
                                MarketState.opportunity_theme_items,
                                _opportunity_theme_card,
                            ),
                            columns=rx.breakpoints(initial="1", md="2", xl="3"),
                            spacing="2",
                            width="100%",
                            margin_top="0.5rem",
                        ),
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    MarketState.trend_ranking_items.length() > 0,
                    rx.vstack(
                        rx.foreach(MarketState.trend_ranking_items, _trend_rank_row),
                        width="100%",
                        spacing="1",
                    ),
                    rx.text("ランキングを算出できません。", size="2", color="gray"),
                ),
                width="100%",
                align_items="start",
                spacing="3",
            ),
            width="100%",
        ),
        width="100%",
    )


def _strategy_regime_panel() -> rx.Component:
    return rx.box(
        rx.cond(
            MarketState.strategy_regime.label != "",
            rx.hstack(
                rx.vstack(
                    rx.text("戦略レジーム", size="2", weight="bold"),
                    rx.hstack(
                        rx.badge(
                            MarketState.strategy_regime.label,
                            color_scheme=_strategy_color(
                                MarketState.strategy_regime.key
                            ),
                            size="3",
                        ),
                        rx.badge(
                            "リスク枠 " + MarketState.strategy_regime.risk_budget,
                            color_scheme="gray",
                            variant="surface",
                        ),
                        spacing="2",
                        wrap="wrap",
                    ),
                    rx.text(
                        MarketState.strategy_regime.rationale,
                        size="2",
                        color=rx.color("gray", 11),
                    ),
                    rx.text(
                        "無効化: " + MarketState.strategy_regime.invalidation,
                        size="1",
                        color=rx.color("gray", 10),
                    ),
                    align_items="start",
                    spacing="2",
                    flex="1",
                ),
                rx.grid(
                    rx.foreach(MarketState.market_timeframes, _timeframe_card),
                    columns=rx.breakpoints(initial="1", md="3"),
                    spacing="2",
                    flex="2",
                ),
                align_items="start",
                width="100%",
                spacing="3",
            ),
            rx.fragment(),
        ),
        rx.cond(
            MarketState.important_levels.length() > 0,
            rx.box(
                rx.text("重要水準", weight="bold", size="2", margin_top="0.75rem"),
                rx.grid(
                    rx.foreach(MarketState.important_levels, _important_level_card),
                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="2",
                    width="100%",
                    margin_top="0.5rem",
                ),
            ),
            rx.fragment(),
        ),
        rx.cond(
            MarketState.market_drivers.length() > 0,
            rx.box(
                rx.text("判断材料", weight="bold", size="2", margin_top="0.75rem"),
                rx.grid(
                    rx.foreach(MarketState.market_drivers, _market_driver_row),
                    columns=rx.breakpoints(initial="1", md="2", xl="3"),
                    spacing="2",
                    width="100%",
                    margin_top="0.5rem",
                ),
            ),
            rx.fragment(),
        ),
        width="100%",
        padding="0.75rem",
        border=f"1px solid {rx.color('green', 5)}",
        border_radius="8px",
        bg=rx.color("green", 2),
    )


def _timeframe_card(item) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(item.label, weight="bold", size="1"),
                rx.spacer(),
                rx.badge(
                    item.confidence, color_scheme=_confidence_color(item.confidence)
                ),
                width="100%",
            ),
            rx.hstack(
                rx.badge(item.market_tone, color_scheme=_tone_color(item.market_tone)),
                rx.badge(item.direction_label, color_scheme="gray", variant="surface"),
                spacing="1",
                wrap="wrap",
            ),
            rx.text("score " + item.score_str, size="1", color=rx.color("gray", 10)),
            align_items="start",
            spacing="1",
        ),
        padding="0.55rem",
    )


def _important_level_card(item) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(item.label, weight="bold", size="2"),
                rx.text(item.ticker, size="1", color=rx.color("gray", 10)),
                rx.spacer(),
                rx.badge(
                    item.behavior_label, color_scheme=_behavior_color(item.behavior)
                ),
                width="100%",
                align_items="center",
            ),
            rx.text(
                "終値 " + item.close_str + " / 1日 " + item.change_1d_str,
                size="1",
                color=rx.color("gray", 10),
            ),
            rx.text(
                "支持 "
                + item.support_str
                + " / 下値 "
                + item.lower_support_str
                + " / 抵抗 "
                + item.resistance_str,
                size="1",
                color=rx.color("gray", 10),
            ),
            rx.cond(
                item.volume_profile_summary != "",
                rx.text(
                    "価格帯別出来高: " + item.volume_profile_summary,
                    size="1",
                    weight="medium",
                    color=rx.color("blue", 10),
                ),
                rx.fragment(),
            ),
            rx.cond(
                item.proxy_note != "",
                rx.text(
                    item.proxy_note,
                    size="1",
                    color=rx.color("gray", 9),
                ),
                rx.fragment(),
            ),
            rx.text(
                "20MA "
                + item.ma20_str
                + " / 50MA "
                + item.ma50_str
                + " / 200MA "
                + item.ma200_str,
                size="1",
                color=rx.color("gray", 9),
            ),
            align_items="start",
            spacing="1",
        ),
        padding="0.55rem",
    )


def _market_driver_row(item) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(item.label, weight="bold", size="2"),
                rx.text(item.value_str, size="2", weight="bold"),
                rx.spacer(),
                rx.badge(item.interpretation, color_scheme="gray", variant="surface"),
                width="100%",
                align_items="center",
            ),
            rx.text(
                "5日 " + item.change_5d_str + " / 20日 " + item.change_20d_str,
                size="1",
                color=rx.color("gray", 10),
            ),
            align_items="start",
            spacing="1",
        ),
        padding="0.55rem",
    )


def _trend_rank_row(item) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.badge("#" + item.rank.to_string(), color_scheme="blue", width="48px"),
            rx.vstack(
                rx.hstack(
                    rx.text(item.theme, weight="bold", size="2"),
                    rx.badge(
                        item.parent_sector, color_scheme="gray", variant="surface"
                    ),
                    rx.cond(
                        item.proxy_ticker != "",
                        rx.badge(
                            item.proxy_ticker, color_scheme="cyan", variant="surface"
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                    wrap="wrap",
                ),
                rx.text(
                    "1週 "
                    + item.performance_1w_str
                    + " / 1ヶ月 "
                    + item.performance_1m_str
                    + " / 6ヶ月 "
                    + item.performance_6m_str
                    + " / Flow "
                    + item.flow_score_str,
                    size="1",
                    color=rx.color("gray", 10),
                ),
                rx.cond(
                    (item.option_summary != "")
                    | (item.representative_tickers.length() > 0),
                    _trend_rank_details(item),
                    rx.fragment(),
                ),
                align_items="start",
                spacing="1",
                flex="1",
            ),
            rx.vstack(
                rx.badge(
                    item.total_score_str,
                    color_scheme=_score_color(item.total_score),
                    variant="surface",
                ),
                rx.badge(
                    _option_label(item.option_asymmetry),
                    color_scheme=_option_color(item.option_asymmetry),
                    variant="surface",
                ),
                align_items="end",
                spacing="1",
            ),
            width="100%",
            align_items="start",
            spacing="3",
        ),
        width="100%",
        padding_y="0.55rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
    )


def _trend_rank_details(item) -> rx.Component:
    return rx.accordion.root(
        rx.accordion.item(
            header="詳細",
            content=rx.vstack(
                rx.cond(
                    item.option_summary != "",
                    rx.text(
                        item.option_summary,
                        size="1",
                        color=rx.color("gray", 10),
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    item.representative_tickers.length() > 0,
                    rx.hstack(
                        rx.text("代表銘柄", size="1", color=rx.color("gray", 10)),
                        rx.foreach(
                            item.representative_tickers,
                            lambda ticker: rx.badge(
                                ticker, color_scheme="gray", variant="surface"
                            ),
                        ),
                        spacing="1",
                        wrap="wrap",
                    ),
                    rx.fragment(),
                ),
                width="100%",
                align_items="start",
                spacing="1",
            ),
        ),
        type="single",
        collapsible=True,
        width="100%",
    )


def _opportunity_theme_card(item) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(item.theme, weight="bold", size="2", flex="1"),
                rx.badge(item.label, color_scheme="green", variant="surface"),
                width="100%",
                align_items="center",
            ),
            rx.hstack(
                rx.cond(
                    item.parent_sector != "",
                    rx.badge(item.parent_sector, color_scheme="gray", variant="soft"),
                    rx.fragment(),
                ),
                rx.cond(
                    item.proxy_ticker != "",
                    rx.badge(
                        "ETF " + item.proxy_ticker,
                        color_scheme="cyan",
                        variant="surface",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    item.option_proxy_ticker != "",
                    rx.badge(
                        "Option " + item.option_proxy_ticker,
                        color_scheme="blue",
                        variant="surface",
                    ),
                    rx.fragment(),
                ),
                spacing="1",
                wrap="wrap",
            ),
            rx.text(item.reason, size="1", color=rx.color("gray", 10)),
            rx.text(
                "無効化: " + item.invalidation,
                size="1",
                color=rx.color("gray", 9),
            ),
            rx.hstack(
                rx.badge("rank " + item.rank.to_string(), color_scheme="blue"),
                rx.badge(item.opportunity_score_str, color_scheme="green"),
                rx.badge(
                    _option_label(item.option_asymmetry),
                    color_scheme=_option_color(item.option_asymmetry),
                    variant="surface",
                ),
                spacing="1",
                wrap="wrap",
            ),
            align_items="start",
            spacing="1",
        ),
        padding="0.65rem",
    )


def _ibd_regime_panel() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text("IBD式市場状態", size="2", weight="bold"),
                rx.hstack(
                    rx.badge(
                        MarketState.ibd_regime.label,
                        color_scheme=_regime_color(MarketState.ibd_regime.status_key),
                        size="3",
                    ),
                    rx.badge(
                        "想定リスク: " + MarketState.ibd_regime.exposure_level,
                        color_scheme="gray",
                        variant="surface",
                    ),
                    spacing="2",
                    wrap="wrap",
                ),
                rx.text(
                    MarketState.ibd_regime.rationale,
                    size="2",
                    color=rx.color("gray", 11),
                ),
                align_items="start",
                spacing="2",
            ),
            rx.spacer(),
            rx.text(
                "weight "
                + MarketState.ibd_regime.weight.to_string()
                + " / score "
                + MarketState.ibd_regime.score.to_string(),
                size="2",
                color=rx.color("gray", 10),
            ),
            width="100%",
            align_items="start",
        ),
        width="100%",
        padding="0.75rem",
        border=f"1px solid {rx.color('blue', 5)}",
        border_radius="8px",
        bg=rx.color("blue", 2),
    )


def _playbook_panel() -> rx.Component:
    return rx.box(
        rx.text("現在考えるべきこと / 市場スタンス", weight="bold", size="2"),
        rx.text(
            MarketState.regime_playbook.stance,
            size="2",
            color=rx.color("gray", 11),
            margin_top="0.25rem",
        ),
        rx.grid(
            _playbook_list("考えること", MarketState.regime_playbook.think_about),
            _playbook_list("今やること", MarketState.regime_playbook.do_now),
            _playbook_list("避けること", MarketState.regime_playbook.avoid),
            columns=rx.breakpoints(initial="1", md="3"),
            spacing="3",
            width="100%",
            margin_top="0.75rem",
        ),
        width="100%",
        padding="0.75rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
    )


def _playbook_list(title: str, rows) -> rx.Component:
    return rx.vstack(
        rx.text(title, weight="bold", size="1", color=rx.color("gray", 10)),
        rx.cond(
            rows.length() > 0,
            rx.foreach(rows, lambda item: rx.text("- ", item, size="1")),
            rx.text("-", size="1", color="gray"),
        ),
        align_items="start",
        spacing="1",
    )


def _distortion_column(title: str, rows, color: str) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(title, weight="bold", size="3", color=rx.color(color, 10)),
            rx.cond(
                rows.length() > 0,
                rx.vstack(rx.foreach(rows, _distortion_item), width="100%"),
                rx.text("候補なし", size="2", color="gray"),
            ),
            width="100%",
            align_items="start",
        ),
        width="100%",
    )


def _distortion_item(item) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(item.theme, weight="bold", size="2"),
            rx.spacer(),
            rx.badge(
                "乖離 " + item.distortion_score_str,
                color_scheme=rx.cond(
                    item.distortion_score_str == "算出不可",
                    "gray",
                    rx.cond(item.distortion_score >= 0, "green", "red"),
                ),
            ),
            width="100%",
        ),
        rx.text(
            "ファンダメンタル "
            + item.fundamental_score_str
            + "（網羅率 "
            + item.fundamental_coverage_str
            + "） / フロー "
            + item.flow_score_str
            + "（網羅率 "
            + item.flow_coverage_str
            + "）",
            size="1",
            color=rx.color("gray", 10),
        ),
        rx.text(item.rationale, size="1", color=rx.color("gray", 11)),
        rx.cond(
            item.tickers.length() > 0,
            rx.hstack(
                rx.foreach(
                    item.tickers,
                    lambda ticker: rx.badge(
                        ticker,
                        variant="surface",
                        color_scheme="gray",
                    ),
                ),
                spacing="1",
                wrap="wrap",
                margin_top="0.35rem",
            ),
            rx.fragment(),
        ),
        width="100%",
        padding_y="0.5rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
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


def _credit_and_flow_panel() -> rx.Component:
    return rx.box(
        rx.text(
            "信用ストレス速度 / ETFリーダーシップproxy",
            weight="bold",
            size="2",
            margin_bottom="0.5rem",
        ),
        rx.grid(
            _credit_stress_card(),
            _flow_proxy_card(),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="2",
            width="100%",
        ),
        width="100%",
        margin_top="1rem",
        padding="0.75rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
    )


def _credit_stress_card() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text("信用ストレス速度", weight="bold", size="1"),
            rx.spacer(),
            rx.badge(
                MarketState.credit_stress.status_label,
                color_scheme=_level_color(MarketState.credit_stress.level),
            ),
            width="100%",
            align_items="center",
        ),
        rx.text(
            MarketState.credit_stress.summary,
            size="1",
            color=rx.color("gray", 10),
            margin_top="0.25rem",
        ),
        rx.vstack(
            rx.foreach(
                MarketState.credit_stress.indicators,
                _credit_indicator_row,
            ),
            width="100%",
            spacing="1",
            margin_top="0.5rem",
        ),
        rx.cond(
            MarketState.credit_stress.confirmations.length() > 0,
            rx.box(
                rx.text(
                    "確認指標",
                    size="1",
                    weight="bold",
                    color=rx.color("gray", 10),
                    margin_top="0.5rem",
                ),
                rx.vstack(
                    rx.foreach(
                        MarketState.credit_stress.confirmations,
                        _credit_confirmation_row,
                    ),
                    width="100%",
                    spacing="1",
                    margin_top="0.25rem",
                ),
            ),
            rx.fragment(),
        ),
        width="100%",
        padding="0.65rem",
        border=f"1px solid {rx.color('gray', 3)}",
        border_radius="6px",
    )


def _credit_indicator_row(item) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(item.label, size="2", weight="medium"),
            rx.spacer(),
            rx.badge("z " + item.z_score_str, color_scheme=_level_color(item.level)),
            width="100%",
            align_items="center",
        ),
        rx.text(
            "水準 ",
            item.latest_str,
            " / 3か月 ",
            item.delta_3m_str,
            " / ",
            item.latest_date,
            size="1",
            color=rx.color("gray", 10),
        ),
        padding_y="0.25rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
    )


def _credit_confirmation_row(item) -> rx.Component:
    return rx.hstack(
        rx.text(item.label, size="1", flex="1"),
        rx.badge(item.delta_3m_str, color_scheme=_level_color(item.level)),
        width="100%",
        align_items="center",
    )


def _flow_proxy_card() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text("ETFリーダーシップproxy", weight="bold", size="1"),
            rx.spacer(),
            rx.badge(MarketState.flow_monitor.status, color_scheme="gray"),
            width="100%",
            align_items="center",
        ),
        rx.text(
            MarketState.flow_monitor.summary,
            size="1",
            color=rx.color("gray", 10),
            margin_top="0.25rem",
        ),
        rx.grid(
            rx.box(
                rx.text("流入proxy上位", size="1", weight="bold"),
                rx.vstack(
                    rx.foreach(MarketState.flow_monitor.leaders, _flow_proxy_row),
                    width="100%",
                    spacing="1",
                    margin_top="0.35rem",
                ),
            ),
            rx.box(
                rx.text("流出proxy上位", size="1", weight="bold"),
                rx.vstack(
                    rx.foreach(MarketState.flow_monitor.laggards, _flow_proxy_row),
                    width="100%",
                    spacing="1",
                    margin_top="0.35rem",
                ),
            ),
            columns=rx.breakpoints(initial="1", lg="2"),
            spacing="2",
            width="100%",
            margin_top="0.5rem",
        ),
        width="100%",
        padding="0.65rem",
        border=f"1px solid {rx.color('gray', 3)}",
        border_radius="6px",
    )


def _flow_proxy_row(item) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(item.label, size="2", weight="medium", flex="1"),
            rx.text(item.ticker, size="1", color=rx.color("gray", 10)),
            rx.badge(
                item.leadership_score_str,
                color_scheme=_level_color(item.level),
            ),
            width="100%",
            align_items="center",
        ),
        rx.text(
            "20日相対 ",
            item.relative_return_20d_str,
            " / 60日相対 ",
            item.relative_return_60d_str,
            " / flow z ",
            item.flow_pressure_z_str,
            size="1",
            color=rx.color("gray", 10),
        ),
        padding_y="0.3rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
        width="100%",
    )


def _sector_flow_panel() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(
                "セクター/テーマ資金流入判定",
                weight="bold",
                size="2",
            ),
            rx.spacer(),
            rx.text(
                MarketState.sector_flow_summary,
                size="1",
                color=rx.color("gray", 10),
            ),
            width="100%",
            align_items="center",
        ),
        rx.cond(
            MarketState.flow_alignment.summary != "",
            rx.box(
                rx.hstack(
                    rx.badge(
                        MarketState.flow_alignment.alignment_label,
                        color_scheme="blue",
                        variant="surface",
                    ),
                    rx.text(
                        MarketState.flow_alignment.summary,
                        size="1",
                        color=rx.color("gray", 10),
                    ),
                    width="100%",
                    align_items="center",
                    spacing="2",
                ),
                rx.text(
                    "ETF proxy: "
                    + MarketState.flow_alignment.etf_role
                    + " / Sector flow: "
                    + MarketState.flow_alignment.sector_role,
                    size="1",
                    color=rx.color("gray", 9),
                    margin_top="0.2rem",
                ),
                margin_top="0.5rem",
            ),
            rx.fragment(),
        ),
        rx.cond(
            MarketState.cross_market_stance != "",
            rx.text(
                MarketState.cross_market_stance,
                size="1",
                color=rx.color("gray", 10),
                margin_top="0.25rem",
            ),
            rx.fragment(),
        ),
        rx.grid(
            rx.foreach(MarketState.sector_flow_groups, _sector_flow_group),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="2",
            width="100%",
            margin_top="0.75rem",
        ),
        width="100%",
        margin_top="1rem",
        padding="0.75rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
    )


def _sector_flow_group(group) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(group.market_label, weight="bold", size="2"),
                rx.spacer(),
                rx.text(group.summary, size="1", color=rx.color("gray", 10)),
                width="100%",
                align_items="center",
            ),
            rx.cond(
                group.leaders.length() > 0,
                rx.vstack(
                    rx.foreach(group.leaders, _sector_flow_row),
                    width="100%",
                    spacing="1",
                ),
                rx.text("判定できるデータがありません", size="1", color="gray"),
            ),
            width="100%",
            spacing="2",
        ),
        padding="0.75rem",
    )


def _sector_flow_row(item) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(item.theme, weight="medium", size="2"),
            rx.spacer(),
            rx.badge(item.flow_score_str, color_scheme=_score_color(item.flow_score)),
            rx.badge(item.action, color_scheme=_action_color(item.action)),
            align_items="center",
            width="100%",
        ),
        rx.hstack(
            rx.text("確信度", size="1", color=rx.color("gray", 10)),
            rx.badge(item.confidence, color_scheme=_confidence_color(item.confidence)),
            rx.text("継続性", size="1", color=rx.color("gray", 10)),
            rx.badge(
                item.continuation, color_scheme=_confidence_color(item.continuation)
            ),
            rx.text("5日", size="1", color=rx.color("gray", 10)),
            rx.text(item.change_5d_str, size="1", weight="bold"),
            wrap="wrap",
            spacing="2",
            margin_top="0.25rem",
        ),
        rx.text(
            "相対 ",
            item.relative_1d_str,
            " / 出来高 ",
            item.volume_ratio_str,
            " / 参加率 ",
            item.participation_str,
            size="1",
            color=rx.color("gray", 10),
            margin_top="0.25rem",
        ),
        padding_y="0.4rem",
        border_bottom=f"1px solid {rx.color('gray', 3)}",
        width="100%",
    )


def _nikkei_conditions_panel() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text("日経平均上昇の6条件", weight="bold", size="2"),
            rx.badge(
                MarketState.japan_conditions_score_label,
                color_scheme=_nikkei_score_color(MarketState.japan_conditions_score),
            ),
            rx.spacer(),
            rx.text(
                MarketState.japan_conditions_summary,
                size="1",
                color=rx.color("gray", 10),
            ),
            width="100%",
            align_items="center",
        ),
        rx.grid(
            rx.foreach(MarketState.japan_conditions, _nikkei_condition_card),
            columns=rx.breakpoints(initial="1", md="2", lg="3"),
            spacing="2",
            width="100%",
            margin_top="0.75rem",
        ),
        width="100%",
        margin_top="1rem",
        padding="0.75rem",
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="8px",
    )


def _nikkei_condition_card(item) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    rx.text("C", item.condition_no.to_string()),
                    color_scheme="gray",
                ),
                rx.text(item.title, weight="bold", size="1", flex="1"),
                rx.badge(
                    item.status_label,
                    color_scheme=_condition_status_color(item.status),
                ),
                width="100%",
                align_items="center",
            ),
            rx.text(item.value, size="2", weight="bold"),
            rx.text(item.assessment, size="1", color=rx.color("gray", 11)),
            rx.text(item.evidence, size="1", color=rx.color("gray", 9)),
            spacing="1",
            align_items="start",
        ),
        padding="0.65rem",
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
                MarketState.market_monitor.yield_spread.available,
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
                rx.badge("利用不可", color_scheme="gray", variant="surface"),
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


def _regime_color(status_key) -> rx.Var:
    return rx.cond(
        status_key == "confirmed_uptrend",
        "green",
        rx.cond(
            status_key == "uptrend_under_pressure",
            "orange",
            rx.cond(status_key == "rally_attempt", "yellow", "red"),
        ),
    )


def _score_color(score) -> rx.Var:
    return rx.cond(
        score >= 45,
        "green",
        rx.cond(score >= 20, "blue", rx.cond(score < 0, "red", "gray")),
    )


def _action_color(action) -> rx.Var:
    return rx.cond(
        action == "乗る候補",
        "green",
        rx.cond(
            action == "押し目待ち", "blue", rx.cond(action == "見送り", "red", "gray")
        ),
    )


def _confidence_color(value) -> rx.Var:
    return rx.cond(
        value == "高",
        "green",
        rx.cond(value == "中", "orange", rx.cond(value == "低", "gray", "gray")),
    )


def _condition_status_color(status) -> rx.Var:
    return rx.cond(
        status == "met",
        "green",
        rx.cond(
            status == "not_met",
            "orange",
            rx.cond(status == "unavailable", "gray", "gray"),
        ),
    )


def _nikkei_score_color(score) -> rx.Var:
    return rx.cond(
        score >= 0.65,
        "green",
        rx.cond(score >= 0.4, "orange", "gray"),
    )


def _strategy_color(key) -> rx.Var:
    return rx.cond(
        key == "aggressive_trend_following",
        "green",
        rx.cond(
            key == "trend_following",
            "blue",
            rx.cond(
                key == "mean_reversion",
                "orange",
                rx.cond(key == "aggressive_mean_reversion", "red", "gray"),
            ),
        ),
    )


def _tone_color(tone) -> rx.Var:
    return rx.cond(
        tone == "強気",
        "green",
        rx.cond(tone == "弱気", "red", "gray"),
    )


def _behavior_color(behavior) -> rx.Var:
    return rx.cond(
        behavior == "breakout",
        "green",
        rx.cond(
            behavior == "support_bounce",
            "blue",
            rx.cond(
                behavior == "breakdown",
                "red",
                rx.cond(behavior == "resistance", "orange", "gray"),
            ),
        ),
    )


def _option_label(value) -> rx.Var:
    return rx.cond(
        value == "upside_squeeze_candidate",
        "上方向GEX",
        rx.cond(
            value == "downside_vol_expansion",
            "下方向警戒",
            rx.cond(
                value == "pinning_resistance",
                "抵抗/Pin",
                rx.cond(value == "pinning", "中立/Pin", "Options未取得"),
            ),
        ),
    )


def _option_color(value) -> rx.Var:
    return rx.cond(
        value == "upside_squeeze_candidate",
        "green",
        rx.cond(
            value == "downside_vol_expansion",
            "red",
            rx.cond(value == "pinning_resistance", "orange", "gray"),
        ),
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
