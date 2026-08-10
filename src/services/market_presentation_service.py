"""Presentation formatting for Market Intelligence state."""

from __future__ import annotations

from typing import Any

from src.services.analysis_context import MarketContext
from src.services.market_presentation_models import (
    ClimaxData as ClimaxData,
)
from src.services.market_presentation_models import (
    CompositeEvidenceDisplay,
    CompositeSentimentDisplay,
    CreditStressDisplay,
    CreditStressIndicator,
    DistortionItem,
    FlowAlignmentDisplay,
    FlowProxyDisplay,
    FlowProxyItem,
    IbdBenchmarkDisplay,
    IbdRegimeDisplay,
    ImportantLevelDisplay,
    JapanConditionDisplay,
    MarketDisplayContext,
    MarketDriverDisplay,
    MarketMonitorData,
    MarketSignal,
    MicrostructureData,
    MomentumCategory,
    MomentumTheme,
    OpportunityThemeDisplay,
    OptionSummary,
    RegimePlaybookDisplay,
    SectorFlowGroup,
    SectorFlowItem,
    ShortForecastDisplay,
    StageStatusDisplay,
    StrategyRegimeDisplay,
    TimeframeOutlookDisplay,
    TrendRankingDisplay,
    VixSqAlertDisplay,
)
from src.services.market_presentation_models import (
    DistributionData as DistributionData,
)
from src.services.market_presentation_models import (
    OptionHorizonSummary as OptionHorizonSummary,
)
from src.services.market_presentation_models import (
    SpreadItem as SpreadItem,
)
from src.services.market_presentation_models import (
    Spreads as Spreads,
)
from src.services.market_presentation_models import (
    YieldSpreadData as YieldSpreadData,
)


def build_market_display_context(context: MarketContext) -> MarketDisplayContext:
    """Convert a market analysis context into Reflex-safe display models."""

    indices_data, sectors_data, others_data = _market_lists(
        context.market_data, context.market_config
    )
    distortions = context.market_distortions or {}
    return MarketDisplayContext(
        option_analysis=[
            OptionSummary(**item)
            for item in format_option_summaries(context.options.items)
        ],
        evaluation=context.evaluation,
        market_signals=_format_signals(context.evaluation),
        microstructure=_format_microstructure(context.microstructure),
        momentum_data=_format_momentum(context.momentum),
        market_monitor=MarketMonitorData(**context.monitor)
        if context.monitor
        else MarketMonitorData(),
        ibd_regime=_format_ibd_regime(context.ibd_regime),
        regime_playbook=_format_playbook(context.regime_playbook),
        bullish_distortions=_format_distortions(distortions.get("bullish", [])),
        bearish_distortions=_format_distortions(distortions.get("bearish", [])),
        sector_flow_groups=_format_sector_flow(context.sector_flow),
        sector_flow_summary=context.sector_flow.get("summary", ""),
        cross_market_stance=context.cross_market.get("stance", ""),
        credit_stress=_format_credit_stress(context.credit_stress),
        flow_monitor=_format_flow_monitor(context.flow_monitor),
        vix_sq_alert=_format_vix_sq_alert(context.vix_sq_alert),
        flow_alignment=_format_flow_alignment(context.flow_alignment),
        strategy_regime=_format_strategy_regime(context.strategy_regime),
        market_timeframes=_format_timeframes(context.market_timeframes),
        short_horizon_forecasts=_format_short_horizon_forecasts(
            context.short_horizon_forecast
        ),
        composite_sentiment_items=_format_composite_sentiment(
            context.composite_sentiment
        ),
        important_levels=_format_important_levels(context.important_levels),
        important_levels_summary=context.important_levels.get("summary", ""),
        market_drivers=_format_market_drivers(context.market_driver_monitor),
        market_drivers_summary=context.market_driver_monitor.get("summary", ""),
        trend_ranking_items=_format_trend_ranking(context.trend_ranking),
        trend_ranking_summary=context.trend_ranking.get("summary", ""),
        opportunity_theme_items=_format_opportunities(context.opportunity_themes),
        opportunity_theme_summary=context.opportunity_themes.get("summary", ""),
        detail_stages=_format_detail_stages(context.detail_stages),
        japan_conditions=_format_japan_conditions(context.japan_conditions),
        japan_conditions_summary=context.japan_conditions.get("summary", ""),
        japan_conditions_score_label=context.japan_conditions.get("score_label", ""),
        japan_conditions_score=float(context.japan_conditions.get("score", 0.0)),
        indices_data=indices_data,
        sectors_data=sectors_data,
        others_data=others_data,
        watch_indices_data=[
            item
            for item in indices_data
            if item.get("name") in {"S&P 500", "Nasdaq 100"}
        ],
    )


def format_option_summaries(option_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return Reflex-safe option summary dictionaries."""

    formatted: list[dict[str, Any]] = []
    for opt in option_data:
        pcr = opt.get("pcr") or {}
        gex = opt.get("gex")
        pcr_val = float(pcr.get("volume_pcr", 0.0))
        has_gex = isinstance(gex, dict) and gex.get("nearby_net_gex") is not None
        gex_val = float(gex.get("nearby_net_gex", 0.0)) if has_gex else 0.0
        current_price = float(opt.get("current_price") or 0.0)
        iv_val = opt.get("iv")
        max_pain = opt.get("max_pain")
        formatted.append(
            {
                "ticker": opt.get("ticker", ""),
                "sentiment": opt.get("sentiment", "Neutral"),
                "current_price": current_price,
                "current_price_str": f"${current_price:,.2f}"
                if current_price > 0
                else "",
                "pcr_vol": pcr_val,
                "pcr_vol_str": f"{pcr_val:.2f}",
                "net_gex": gex_val,
                "net_gex_str": f"{gex_val / 1e6:+.0f}M" if has_gex else "-",
                "net_gex_available": has_gex,
                "iv": f"{iv_val * 100:.1f}%" if iv_val is not None else "-",
                "max_pain": f"${max_pain:.0f}" if max_pain is not None else "-",
                "analysis": opt.get("analysis", []),
                "data_quality": opt.get("data_quality", "unavailable"),
                "quality_warnings": list(opt.get("quality_warnings") or []),
                "source": str(opt.get("source") or ""),
                "data_as_of": str(opt.get("data_as_of") or ""),
                "data_mode": str(opt.get("data_mode") or ""),
                "provider_active": bool(opt.get("provider_active", False)),
                "fallback_reason": str(opt.get("fallback_reason") or ""),
                "gamma_coverage": _optional_float(opt.get("gamma_coverage")),
                "gamma_coverage_str": _coverage_str(opt.get("gamma_coverage")),
                "complete_status": str(opt.get("complete_status") or "unavailable"),
                "complete_status_label": _option_complete_label(
                    opt.get("complete_status")
                ),
                "horizons": _format_option_horizons(list(opt.get("horizons") or [])),
                "term_structure_summary": str(
                    (opt.get("term_structure") or {}).get("summary") or ""
                ),
            }
        )
    return formatted


def _format_option_horizons(horizons: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in horizons[:3]:
        skew_detail = item.get("skew_detail") or {}
        skew_method = str(skew_detail.get("method") or "legacy_proxy")
        skew_status = str(skew_detail.get("status") or "proxy")
        skew_value = skew_detail.get("value", item.get("skew"))
        price_range = item.get("price_range")
        lower = item.get("price_range_lower")
        upper = item.get("price_range_upper")
        if isinstance(price_range, (list, tuple)) and len(price_range) >= 2:
            lower, upper = price_range[0], price_range[1]
        rows.append(
            {
                "key": str(item.get("key") or ""),
                "label": str(item.get("label") or ""),
                "dte": _days_str(item.get("dte")),
                "expiration": str(item.get("resolved_expiration") or ""),
                "iv": _ratio_percent_str(item.get("iv")),
                "expected_move": _ratio_percent_str(item.get("expected_move_pct")),
                "price_range": _range_str(lower, upper),
                "pcr_vol": _number_str((item.get("pcr") or {}).get("volume_pcr")),
                "skew": _ratio_percent_str(skew_value),
                "skew_label": (
                    "25Δ IVスキュー"
                    if skew_method == "delta_25_direct"
                    else "10% OTM IVスキュー"
                    if skew_method in {"moneyness_10pct_proxy", "legacy_proxy"}
                    else "IVスキュー"
                ),
                "skew_method": skew_method,
                "skew_status": skew_status,
                "skew_status_label": {
                    "direct": "direct",
                    "proxy": "proxy・表示のみ",
                    "unavailable": "未取得",
                }.get(skew_status, "未取得"),
                "skew_liquidity": str(skew_detail.get("liquidity_status") or "unknown"),
                "gex": _gex_direction((item.get("gex") or {}).get("nearby_net_gex")),
                "data_quality": str(item.get("data_quality") or "unavailable"),
            }
        )
    return rows


def _format_signals(evaluation: dict[str, Any]) -> list[MarketSignal]:
    signals = []
    for signal in evaluation.get("signals", []):
        score = float(signal.get("score", 0.0))
        signals.append(
            MarketSignal(
                name=signal.get("name", ""),
                score=score,
                weight=float(signal.get("weight", 0.0)),
                rationale=signal.get("rationale", ""),
                category="bullish"
                if score >= 0.3
                else "bearish"
                if score <= -0.3
                else "neutral",
            )
        )
    return signals


def _format_microstructure(data: dict[str, Any]) -> MicrostructureData:
    if not data:
        return MicrostructureData()
    cta = data.get("cta_proxy") or {}
    liq = data.get("liquidity") or {}
    vrp_val = data.get("vrp")
    return MicrostructureData(
        unwind_score=data.get("unwind_score", 0),
        unwind_level=data.get("unwind_level", ""),
        vrp=f"{vrp_val:.2%}" if vrp_val is not None else "-",
        cta_score=cta.get("score", 0),
        cta_extremity=cta.get("extremity", ""),
        liquidity_status=liq.get("status", ""),
        narrative=data.get("narrative_text", ""),
    )


def _format_momentum(raw: dict[str, list[dict[str, Any]]]) -> list[MomentumCategory]:
    result = []
    for category, themes in raw.items():
        theme_list = []
        for item in themes[:3]:
            perf = float(item.get("performance", 0.0))
            theme_list.append(
                MomentumTheme(
                    theme=item.get("theme", ""),
                    performance=perf,
                    performance_str=f"{perf:+.1f}%",
                )
            )
        result.append(
            MomentumCategory(
                category=category,
                period=themes[-1].get("period", "") if themes else "",
                themes=theme_list,
            )
        )
    return result


def _format_ibd_regime(raw: dict[str, Any]) -> IbdRegimeDisplay:
    if not raw:
        return IbdRegimeDisplay()
    benchmarks = []
    raw_benchmarks = raw.get("benchmarks") or {}
    for item in raw_benchmarks.values():
        if isinstance(item, dict):
            benchmarks.append(IbdBenchmarkDisplay(**item))
    return IbdRegimeDisplay(
        status_key=raw.get("status_key", ""),
        label=raw.get("label", ""),
        score=float(raw.get("score", 0.0)),
        weight=float(raw.get("weight", 2.0)),
        exposure_level=raw.get("exposure_level", ""),
        rationale=raw.get("rationale", ""),
        action_summary=raw.get("action_summary", ""),
        benchmarks=benchmarks,
    )


def _format_playbook(raw: dict[str, Any]) -> RegimePlaybookDisplay:
    if not raw:
        return RegimePlaybookDisplay()
    return RegimePlaybookDisplay(
        stance=raw.get("stance", ""),
        risk_budget=raw.get("risk_budget", ""),
        think_about=list(raw.get("think_about", [])),
        do_now=list(raw.get("do_now", [])),
        avoid=list(raw.get("avoid", [])),
    )


def _format_distortions(rows: list[dict[str, Any]]) -> list[DistortionItem]:
    return [
        DistortionItem(
            theme=item.get("theme", ""),
            tickers=list(item.get("tickers", [])),
            fundamental_score=_optional_float(item.get("fundamental_score")),
            flow_score=_optional_float(item.get("flow_score")),
            distortion_score=_optional_float(item.get("distortion_score")),
            fundamental_score_str=_optional_score(item.get("fundamental_score")),
            flow_score_str=_optional_score(item.get("flow_score")),
            distortion_score_str=_optional_score(item.get("distortion_score")),
            fundamental_coverage_str=_coverage_str(item.get("fundamental_coverage")),
            flow_coverage_str=_coverage_str(item.get("flow_coverage")),
            classification=item.get("classification", ""),
            rating=item.get("rating", ""),
            rationale=item.get("rationale", ""),
            fundamental_evidence=list(item.get("fundamental_evidence", [])),
            flow_evidence=list(item.get("flow_evidence", [])),
        )
        for item in rows
        if isinstance(item, dict)
    ]


def _optional_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _optional_score(value: Any) -> str:
    number = _optional_float(value)
    return f"{number:.2f}" if number is not None else "算出不可"


def _format_sector_flow(raw: dict[str, Any]) -> list[SectorFlowGroup]:
    groups = []
    markets = raw.get("markets", {}) if raw else {}
    ordered = [market for market in ("US", "JP") if market in markets]
    ordered.extend(market for market in markets if market not in {"US", "JP"})
    for market in ordered:
        payload = markets.get(market, {})
        leaders = []
        for item in payload.get("leaders", []):
            score = float(item.get("flow_score", 0.0))
            leaders.append(
                SectorFlowItem(
                    market=market,
                    theme=item.get("theme", ""),
                    flow_score=score,
                    flow_score_str=f"{score:+.1f}",
                    confidence=item.get("confidence", ""),
                    continuation=item.get("continuation", ""),
                    action=item.get("action", ""),
                    relative_1d_str=f"{float(item.get('relative_1d', 0.0)):+.2f}pt",
                    change_5d_str=f"{float(item.get('change_5d', 0.0)):+.2f}%",
                    volume_ratio_str=f"{float(item.get('volume_ratio', 0.0)):.2f}x",
                    participation_str=f"{float(item.get('participation', 0.0)):.0%}",
                    evidence=item.get("evidence", ""),
                )
            )
        groups.append(
            SectorFlowGroup(
                market=market,
                market_label="米国" if market == "US" else "日本",
                summary=payload.get("summary", ""),
                leaders=leaders,
            )
        )
    return groups


def _format_japan_conditions(raw: dict[str, Any]) -> list[JapanConditionDisplay]:
    result = []
    for item in (raw.get("items", []) if raw else [])[:5]:
        result.append(
            JapanConditionDisplay(
                condition_no=int(item.get("condition_no", 0)),
                title=item.get("title", ""),
                category=item.get("category", ""),
                status=item.get("status", ""),
                status_label=item.get("status_label", ""),
                value=item.get("value", ""),
                threshold=item.get("threshold", ""),
                score=float(item.get("score", 0.0)),
                assessment=item.get("assessment", ""),
                evidence=item.get("evidence", ""),
            )
        )
    return result


def _format_credit_stress(raw: dict[str, Any]) -> CreditStressDisplay:
    if not raw:
        return CreditStressDisplay()
    return CreditStressDisplay(
        status=raw.get("status", ""),
        status_label=raw.get("status_label", ""),
        level=raw.get("level", "gray"),
        summary=raw.get("summary", ""),
        rapid_stress=bool(raw.get("rapid_stress", False)),
        indicators=[
            _format_credit_indicator(item) for item in raw.get("indicators", [])
        ],
        confirmations=[
            _format_credit_indicator(item) for item in raw.get("confirmations", [])[:6]
        ],
        source=raw.get("source", ""),
        fetched_at=raw.get("fetched_at", ""),
    )


def _format_credit_indicator(item: dict[str, Any]) -> CreditStressIndicator:
    latest = float(item.get("latest", 0.0))
    delta = float(item.get("delta_3m", 0.0))
    z_score = float(item.get("z_score", 0.0))
    return CreditStressIndicator(
        series_id=item.get("series_id", ""),
        label=item.get("label", ""),
        latest=latest,
        latest_str=f"{latest:.2f}",
        latest_date=item.get("latest_date", ""),
        delta_3m=delta,
        delta_3m_str=f"{delta:+.2f}",
        z_score=z_score,
        z_score_str=f"{z_score:+.2f}",
        is_hot=bool(item.get("is_hot", False)),
        level=item.get("level", "gray"),
        warning=item.get("warning", ""),
    )


def _format_vix_sq_alert(raw: dict[str, Any]) -> VixSqAlertDisplay:
    if not raw:
        return VixSqAlertDisplay(summary="VIX×SQ週アラートは未取得です。")
    status = str(raw.get("status") or "")
    level = {
        "hedge_alert": "red",
        "bottoming_candidate": "yellow",
        "vix_uptrend_watch": "yellow",
        "neutral": "green",
    }.get(status, "neutral")
    status_label = {
        "hedge_alert": "ヘッジ警戒",
        "bottoming_candidate": "底打ち候補",
        "vix_uptrend_watch": "VIX上昇監視",
        "neutral": "中立",
        "insufficient_data": "データ不足",
        "unavailable": "未取得",
    }.get(status, status or "未判定")
    vix = raw.get("vix")
    return VixSqAlertDisplay(
        status=status,
        status_label=status_label,
        summary=str(raw.get("summary") or ""),
        score=float(raw.get("score") or 0.0),
        level=level,
        in_sq_week=bool(raw.get("in_sq_week", False)),
        monthly_expiration=str(raw.get("monthly_expiration") or ""),
        vix="-" if vix in (None, "") else f"{float(vix):.2f}",
        macd_cross=str(raw.get("macd_cross") or "none"),
        psar_trend=str(raw.get("psar_trend") or ""),
    )


def _format_flow_monitor(raw: dict[str, Any]) -> FlowProxyDisplay:
    if not raw:
        return FlowProxyDisplay()
    return FlowProxyDisplay(
        status=raw.get("status", ""),
        summary=raw.get("summary", ""),
        leaders=[_format_flow_proxy_item(item) for item in raw.get("leaders", [])],
        laggards=[_format_flow_proxy_item(item) for item in raw.get("laggards", [])],
        source=raw.get("source", ""),
    )


def _format_flow_alignment(raw: dict[str, Any]) -> FlowAlignmentDisplay:
    if not raw:
        return FlowAlignmentDisplay()
    return FlowAlignmentDisplay(
        alignment_label=raw.get("alignment_label", ""),
        summary=raw.get("summary", ""),
        etf_role=raw.get("etf_role", ""),
        sector_role=raw.get("sector_role", ""),
    )


def _format_strategy_regime(raw: dict[str, Any]) -> StrategyRegimeDisplay:
    if not raw:
        return StrategyRegimeDisplay()
    return StrategyRegimeDisplay(
        key=raw.get("key", ""),
        label=raw.get("label", ""),
        rationale=raw.get("rationale", ""),
        risk_budget=raw.get("risk_budget", ""),
        invalidation=raw.get("invalidation", ""),
        evidence=list(raw.get("evidence", [])),
    )


def _format_timeframes(raw: dict[str, Any]) -> list[TimeframeOutlookDisplay]:
    rows = []
    for item in raw.get("items", []) if raw else []:
        score = float(item.get("score", 0.0))
        rows.append(
            TimeframeOutlookDisplay(
                key=item.get("key", ""),
                label=item.get("label", ""),
                score=score,
                score_str=f"{score:+.2f}",
                market_tone=item.get("market_tone", ""),
                direction=item.get("direction", ""),
                direction_label=item.get("direction_label", ""),
                confidence=item.get("confidence", ""),
                evidence=list(item.get("evidence", [])),
            )
        )
    return rows


def _format_short_horizon_forecasts(
    raw: dict[str, Any],
) -> list[ShortForecastDisplay]:
    rows: list[ShortForecastDisplay] = []
    for ticker in ("SPY", "QQQ"):
        target = (raw.get("targets") or {}).get(ticker) or {}
        for horizon in ("1d", "5d", "20d"):
            item = (target.get("horizons") or {}).get(horizon) or {}
            rows.append(
                ShortForecastDisplay(
                    ticker=ticker,
                    horizon=horizon,
                    status=str(item.get("status") or "unavailable"),
                    status_label=_forecast_status_label(item.get("status")),
                    probability_up=_optional_pct(item.get("probability_up")),
                    range_text=_forecast_range(item.get("p10"), item.get("p90")),
                    implied_move=_optional_pct(item.get("implied_expected_move")),
                    risk_level=str(item.get("risk_level") or "unknown"),
                    risk_label=_risk_label(item.get("risk_level")),
                    direction_label=str(item.get("direction_label") or ""),
                    confidence=str(item.get("confidence") or ""),
                    as_of=str(item.get("as_of") or raw.get("as_of") or ""),
                )
            )
    return rows


def _format_composite_sentiment(
    raw: dict[str, Any],
) -> list[CompositeSentimentDisplay]:
    rows: list[CompositeSentimentDisplay] = []
    for ticker in ("SPY", "QQQ"):
        item = (raw.get("targets") or {}).get(ticker) or {}
        evidence = []
        for detail in item.get("evidence", []):
            evidence.append(
                CompositeEvidenceDisplay(
                    label=str(detail.get("label") or ""),
                    status=str(detail.get("status") or "unavailable"),
                    status_label={
                        "met": "成立",
                        "not_met": "不成立",
                        "unavailable": "未取得",
                    }.get(str(detail.get("status") or ""), "未取得"),
                    value=_number_or_percent(detail.get("value")),
                    threshold=str(detail.get("threshold") or ""),
                    source=str(detail.get("source") or ""),
                    detail=_composite_evidence_detail(detail),
                )
            )
        rows.append(
            CompositeSentimentDisplay(
                ticker=ticker,
                state=str(item.get("state") or "mixed"),
                state_label=str(item.get("state_label") or "材料混在"),
                status=str(item.get("status") or "unavailable"),
                status_label={
                    "confirmed": "確認済み",
                    "partial": "一部未確認",
                    "unavailable": "未判定",
                }.get(str(item.get("status") or ""), "未判定"),
                risk_floor=str(item.get("risk_floor") or "none"),
                risk_label=_risk_label(item.get("risk_floor")),
                summary=str(item.get("summary") or ""),
                reversal_watch=bool(item.get("reversal_watch", False)),
                as_of=str(item.get("as_of") or raw.get("as_of") or ""),
                evidence=evidence,
            )
        )
    return rows


def _composite_evidence_detail(detail: dict[str, Any]) -> str:
    if detail.get("metric_kind") != "cboe_skew_index":
        return ""
    parts = []
    raw_value = _optional_float(detail.get("raw_value"))
    percentile = _optional_float(detail.get("percentile"))
    change_5d = _optional_float(detail.get("change_5d"))
    if raw_value is not None:
        parts.append(f"指数値 {raw_value:.2f}")
    if percentile is not None:
        parts.append(f"履歴percentile {percentile:.1f}")
    if change_5d is not None:
        parts.append(f"5日変化 {change_5d:+.1%}")
    if detail.get("as_of"):
        parts.append(f"as-of {detail.get('as_of')}")
    return " / ".join(parts)


def _forecast_status_label(value: Any) -> str:
    return {
        "validated": "検証済み",
        "research_only": "検証不十分",
        "insufficient_data": "データ不足",
        "unavailable": "未算出",
    }.get(str(value or ""), "未算出")


def _risk_label(value: Any) -> str:
    return {
        "extreme": "極端",
        "high": "高",
        "medium": "中",
        "low": "低",
        "none": "補正なし",
        "unknown": "不明",
    }.get(str(value or ""), "不明")


def _optional_pct(value: Any) -> str:
    return "算出不可" if value is None else f"{float(value):.1%}"


def _forecast_range(lower: Any, upper: Any) -> str:
    if lower is None or upper is None:
        return "算出不可"
    return f"{float(lower):+.1%} ～ {float(upper):+.1%}"


def _number_or_percent(value: Any) -> str:
    if value is None:
        return "不明"
    number = float(value)
    return f"{number:+.1%}" if abs(number) <= 2 else f"{number:.2f}"


def _format_important_levels(raw: dict[str, Any]) -> list[ImportantLevelDisplay]:
    rows = []
    for item in raw.get("items", []) if raw else []:
        profile = item.get("volume_profile") or {}
        rows.append(
            ImportantLevelDisplay(
                label=item.get("label", ""),
                ticker=item.get("ticker", ""),
                close_str=_price_str(item.get("close")),
                support_str=_price_str(item.get("support")),
                resistance_str=_price_str(item.get("resistance")),
                lower_support_str=_price_str(item.get("lower_support")),
                ma20_str=_price_str(item.get("ma20")),
                ma50_str=_price_str(item.get("ma50")),
                ma200_str=_price_str(item.get("ma200")),
                change_1d_str=_pct_str(item.get("change_1d")),
                behavior=item.get("behavior", ""),
                behavior_label=item.get("behavior_label", ""),
                volume_profile_summary=profile.get("summary", ""),
                poc_str=_zone_str(profile.get("poc")),
                value_area_str=(
                    f"{_price_str((profile.get('value_area') or {}).get('val'))}～"
                    f"{_price_str((profile.get('value_area') or {}).get('vah'))}"
                    if profile.get("value_area")
                    else ""
                ),
                support_zone_str=_zone_str(profile.get("support_zone")),
                resistance_zone_str=_zone_str(profile.get("resistance_zone")),
                proxy_note=item.get("proxy_note", ""),
                data_quality=item.get("data_quality", "unavailable"),
            )
        )
    return rows


def _format_market_drivers(raw: dict[str, Any]) -> list[MarketDriverDisplay]:
    rows = []
    for item in raw.get("items", []) if raw else []:
        rows.append(
            MarketDriverDisplay(
                label=item.get("label", ""),
                ticker=item.get("ticker", ""),
                value_str=_driver_value_str(item.get("label", ""), item.get("value")),
                change_5d_str=_pct_str(item.get("change_5d")),
                change_20d_str=_pct_str(item.get("change_20d")),
                interpretation=item.get("interpretation", ""),
                data_quality=item.get("data_quality", "unavailable"),
            )
        )
    return rows


def _format_trend_ranking(raw: dict[str, Any]) -> list[TrendRankingDisplay]:
    rows = []
    for item in (raw.get("items", []) if raw else [])[:5]:
        total_score = float(item.get("total_score", 0.0))
        rows.append(
            TrendRankingDisplay(
                rank=int(item.get("rank", 0) or 0),
                theme=item.get("theme", ""),
                parent_sector=item.get("parent_sector", ""),
                proxy_ticker=item.get("proxy_ticker", ""),
                option_proxy_ticker=item.get("option_proxy_ticker", ""),
                total_score=total_score,
                total_score_str=f"{total_score:+.1f}",
                rank_points=int(item.get("rank_points", 0) or 0),
                performance_1w_str=_pct_str(item.get("performance_1w")),
                performance_1m_str=_pct_str(item.get("performance_1m")),
                performance_6m_str=_pct_str(item.get("performance_6m")),
                flow_score_str=_signed_str(item.get("flow_score")),
                participation_str=_ratio_percent_str(item.get("participation")),
                option_asymmetry=item.get("option_asymmetry", "unavailable"),
                option_score_str=_signed_str(item.get("option_score")),
                option_summary=item.get("option_summary", ""),
                option_source=item.get("option_source", ""),
                option_data_as_of=item.get("option_data_as_of", ""),
                option_data_quality=item.get("option_data_quality", ""),
                representative_tickers=list(item.get("representative_tickers", [])),
            )
        )
    return rows


def _format_opportunities(raw: dict[str, Any]) -> list[OpportunityThemeDisplay]:
    rows = []
    for item in raw.get("items", []) if raw else []:
        score = float(item.get("opportunity_score", 0.0))
        rows.append(
            OpportunityThemeDisplay(
                theme=item.get("theme", ""),
                parent_sector=item.get("parent_sector", ""),
                proxy_ticker=item.get("proxy_ticker", ""),
                option_proxy_ticker=item.get("option_proxy_ticker", ""),
                rank=int(item.get("rank", 0) or 0),
                opportunity_score=score,
                opportunity_score_str=f"{score:+.1f}",
                label=item.get("label", ""),
                reason=item.get("reason", ""),
                representative_tickers=list(item.get("representative_tickers", [])),
                option_asymmetry=item.get("option_asymmetry", ""),
                invalidation=item.get("invalidation", ""),
            )
        )
    return rows


def _format_detail_stages(raw: dict[str, dict[str, Any]]) -> list[StageStatusDisplay]:
    stages = []
    for key in (
        "core",
        "theme_flow",
        "volatility_sentiment",
        "credit_distortion",
        "options",
    ):
        item = raw.get(key, {}) if raw else {}
        if not item:
            continue
        stages.append(
            StageStatusDisplay(
                key=item.get("key", key),
                label=item.get("label", key),
                difficulty=item.get("difficulty", ""),
                status=item.get("status", "pending"),
                status_label=item.get("status_label", item.get("status", "pending")),
                cache_status=item.get("cache_status", ""),
                fetched_at=item.get("fetched_at", ""),
                duration_ms=int(item.get("duration_ms", 0) or 0),
                duration_label=(
                    f"{int(item.get('duration_ms', 0) or 0):,} ms"
                    if item.get("duration_ms")
                    else ""
                ),
                summary=item.get("summary", ""),
                target=item.get("target", ""),
                error_message=item.get("error_message", ""),
                quality_warnings=list(item.get("quality_warnings", [])),
            )
        )
    return stages


def _format_flow_proxy_item(item: dict[str, Any]) -> FlowProxyItem:
    score = float(item.get("leadership_score", 0.0))
    flow_z = float(item.get("flow_pressure_z", 0.0))
    return FlowProxyItem(
        ticker=item.get("ticker", ""),
        label=item.get("label", ""),
        leadership_score=score,
        leadership_score_str=f"{score:+.2f}",
        flow_pressure_z=flow_z,
        flow_pressure_z_str=f"{flow_z:+.2f}",
        relative_return_20d_str=(
            f"{float(item.get('relative_return_20d', 0.0)):+.2f}%"
        ),
        relative_return_60d_str=(
            f"{float(item.get('relative_return_60d', 0.0)):+.2f}%"
        ),
        trend_above_ma50=bool(item.get("trend_above_ma50", False)),
        level=item.get("level", "gray"),
    )


def _price_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:,.2f}"


def _coverage_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:.0%}"


def _days_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:.0f}日"


def _number_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:.2f}"


def _range_str(lower: Any, upper: Any) -> str:
    low = _optional_float(lower)
    high = _optional_float(upper)
    if low is None or high is None:
        return "-"
    return f"${low:,.2f}～${high:,.2f}"


def _gex_direction(value: Any) -> str:
    number = _optional_float(value)
    if number is None:
        return "-"
    return "正" if number > 0 else "負"


def _option_complete_label(value: Any) -> str:
    return {
        "complete": "完全取得",
        "partial": "一部取得",
        "partial_greeks": "Greeks一部欠損",
        "gex_unavailable": "GEX不可",
        "fallback": "fallback中",
        "provider_inactive": "直接Greeksなし",
        "stale_cache": "古いキャッシュ",
        "failed": "取得失敗",
        "not_applicable": "対象外",
        "unavailable": "未取得",
    }.get(str(value or "unavailable"), str(value or "未取得"))


def _zone_str(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    low = _price_str(value.get("low"))
    high = _price_str(value.get("high"))
    if low == "-" or high == "-":
        return ""
    return f"{low}～{high}"


def _pct_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:+.2f}%"


def _signed_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:+.1f}"


def _ratio_percent_str(value: Any) -> str:
    number = _optional_float(value)
    return "-" if number is None else f"{number:.0%}"


def _driver_value_str(label: str, value: Any) -> str:
    number = _optional_float(value)
    if number is None:
        return "-"
    return f"{number:.2f}%" if label == "US10Y" else f"{number:,.2f}"


def _market_lists(
    raw_data: dict[str, Any], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    indices = _ordered_market_items(raw_data, config.get("indices", {}))
    sectors = _ordered_market_items(raw_data, config.get("sectors", {}))
    others = [
        *_ordered_market_items(raw_data, config.get("commodities", {})),
        *_ordered_market_items(raw_data, config.get("forex", {})),
        *_ordered_market_items(raw_data, config.get("crypto", {})),
    ]
    return indices, sectors, others


def _ordered_market_items(
    raw_data: dict[str, Any],
    configured: dict[str, str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for name in configured:
        data = raw_data.get(name)
        if not isinstance(data, dict):
            continue
        items.append(_market_item(name, data))
    return items


def _market_item(name: str, data: dict[str, Any]) -> dict[str, Any]:
    price = float(data.get("price", 0.0))
    change = round(float(data.get("change", 0.0)), 1)
    ticker = data.get("ticker", "")
    if "Yield" in name:
        price_text = f"{price:.2f}%"
    elif "JPY" in ticker:
        price_text = f"¥{price:.2f}"
    elif "BTC" in ticker or "ETH" in ticker:
        price_text = f"${price / 1000:.1f}K"
    elif price >= 1000:
        price_text = f"{price:,.0f}"
    else:
        price_text = f"${price:.2f}"
    return {"name": name, "price": price_text, "change": change}
