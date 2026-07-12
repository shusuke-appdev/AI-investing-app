"""Deterministic text projection of market context for AI prompts."""

from src.services.analysis_context import MarketContext
from src.services.market_dashboard_service import DETAIL_STAGE_ORDER
from src.services.market_dashboard_support import (
    _display_percent,
    _nested,
    _ticker_list_text,
)


def format_market_context_for_ai(context: MarketContext) -> str:
    """Create a compact prompt section from already computed monitoring context."""

    parts = ["[Advanced Technical / Market Monitoring]"]
    if context.data_status:
        status_parts = []
        for item in context.data_status[:6]:
            status = "partial" if item.is_partial else "ok"
            if item.is_stale:
                status = "stale"
            error = f", error={item.error}" if item.error else ""
            cache = (
                f", cache={item.cache_status}"
                if item.cache_status and item.cache_status != "live"
                else ""
            )
            status_parts.append(
                f"{item.name}: {status} from {item.source or 'unknown'}{cache}{error}"
            )
        parts.append("- Data status: " + "; ".join(status_parts))
    if context.quality_warnings:
        parts.append("- Data quality: " + "; ".join(context.quality_warnings[:6]))
    if context.provenance:
        parts.append("[Data provenance]")
        for item in context.provenance[:12]:
            details = [
                f"kind={item.kind.value}",
                f"source={item.source or 'unknown'}",
            ]
            if item.as_of:
                details.append(f"as_of={item.as_of}")
            if item.method:
                details.append(f"method={item.method}")
            if item.limitation:
                details.append(f"limitation={item.limitation}")
            details.append(f"risk={item.risk_level}")
            parts.append(f"- {item.label}: " + ", ".join(details))
    if context.detail_stages:
        stage_parts = []
        for key in DETAIL_STAGE_ORDER:
            item = context.detail_stages.get(key) or {}
            if item:
                stage_parts.append(
                    f"{item.get('label', key)}={item.get('status_label', item.get('status', 'unknown'))}"
                )
        if stage_parts:
            parts.append("- Detail stages: " + "; ".join(stage_parts))
    if context.options.quality_warnings:
        parts.append(
            "- Options data quality: " + "; ".join(context.options.quality_warnings[:6])
        )
    if context.options.horizons:
        parts.append("[Options term structure]")
        if context.options.term_structure.get("summary"):
            parts.append(f"- {context.options.term_structure.get('summary')}")
        for item in context.options.horizons[:3]:
            details = [
                f"{item.get('label', item.get('key', ''))}",
            ]
            if item.get("iv") is not None:
                details.append(f"IV={_display_percent(item.get('iv'))}")
            if item.get("expected_move_pct") is not None:
                details.append(
                    f"1sigma_move={_display_percent(item.get('expected_move_pct'))}"
                )
            if item.get("pcr_volume") is not None:
                details.append(f"PCR={float(item.get('pcr_volume')):.2f}")
            if item.get("skew") is not None:
                details.append(f"skew={_display_percent(item.get('skew'))}")
            if item.get("nearby_net_gex") is not None:
                details.append(
                    "nearby_gex="
                    + (
                        "positive"
                        if float(item.get("nearby_net_gex")) > 0
                        else "negative"
                    )
                )
            parts.append("- " + ", ".join(details))
    if context.volatility_regime:
        volatility = context.volatility_regime
        parts.append("[Market volatility regime]")
        parts.append(
            f"- {volatility.get('summary', '')}; "
            f"confidence={volatility.get('confidence', 'low')}"
        )
        outcomes = volatility.get("forward_outcomes", {}).get("20d", {})
        if outcomes:
            parts.append(
                "- Historical analog 20d: "
                f"mean={_display_percent(outcomes.get('mean_return'))}, "
                f"probability_up={_display_percent(outcomes.get('probability_up'))}"
            )
    if context.vix_sq_alert:
        vix_sq = context.vix_sq_alert
        parts.append("[VIX x SQ week alert]")
        parts.append(
            f"- {vix_sq.get('summary', '')}; "
            f"status={vix_sq.get('status', 'unknown')}, "
            f"in_sq_week={vix_sq.get('in_sq_week', False)}, "
            f"expiration={vix_sq.get('monthly_expiration', '')}"
        )
    if context.sentiment:
        parts.append(
            "[Local sentiment composite] "
            f"{context.sentiment.get('summary', '')}; "
            f"coverage={context.sentiment.get('coverage', '')}"
        )
        cnn = context.sentiment.get("cnn_reference") or {}
        if cnn:
            parts.append(
                "- CNN external reference only: "
                f"status={cnn.get('status', 'unavailable')}, "
                f"score={cnn.get('score')}, rating={cnn.get('rating', '')}"
            )
    if context.top_risk_signposts:
        signposts = context.top_risk_signposts
        parts.append(
            "[BofA-inspired top-risk subset, not official BofA] "
            f"{signposts.get('summary', '')}"
        )
        for item in (signposts.get("items") or [])[:7]:
            parts.append(
                f"- {item.get('label', '')}: {item.get('status', 'unknown')} "
                f"({item.get('kind', 'proxy')})"
            )

    strategy = context.strategy_regime or {}
    if strategy:
        parts.append("[Strategy regime]")
        parts.append(
            f"- Selected: {strategy.get('label', 'unknown')} "
            f"risk_budget={strategy.get('risk_budget', '')}"
        )
        if strategy.get("rationale"):
            parts.append(f"- Rationale: {strategy.get('rationale')}")
        if strategy.get("invalidation"):
            parts.append(f"- Invalidation: {strategy.get('invalidation')}")

    timeframes = context.market_timeframes or {}
    if timeframes.get("items"):
        parts.append("[Market direction by timeframe]")
        for item in timeframes.get("items", [])[:3]:
            parts.append(
                f"- {item.get('label')}: {item.get('market_tone')} / "
                f"{item.get('direction_label')} "
                f"(score={float(item.get('score', 0.0)):+.2f}, "
                f"confidence={item.get('confidence', '')})"
            )

    levels = context.important_levels or {}
    if levels.get("items"):
        parts.append("[Important SPY / QQQ levels]")
        for item in levels.get("items", [])[:2]:
            if item.get("data_quality") != "ok":
                continue
            parts.append(
                f"- {item.get('label')} {item.get('ticker')}: "
                f"close={item.get('close')}, support={item.get('support')}, "
                f"resistance={item.get('resistance')}, "
                f"behavior={item.get('behavior_label')}"
            )

    drivers = context.market_driver_monitor or {}
    if drivers.get("items"):
        parts.append("[Macro/volatility drivers]")
        if drivers.get("summary"):
            parts.append(f"- {drivers.get('summary')}")
        for item in drivers.get("items", [])[:6]:
            if item.get("data_quality") != "ok":
                continue
            parts.append(
                f"- {item.get('label')}: value={item.get('value')}, "
                f"5d={float(item.get('change_5d', 0.0)):+.2f}%, "
                f"interpretation={item.get('interpretation', '')}"
            )

    trend = context.trend_ranking or {}
    if trend.get("items"):
        parts.append("[Integrated trend ranking]")
        parts.append(f"- {trend.get('summary', '')}")
        for item in trend.get("items", [])[:5]:
            parts.append(
                f"- #{item.get('rank')} {item.get('theme')} "
                f"score={float(item.get('total_score', 0.0)):.1f}, "
                f"parent={item.get('parent_sector', '')}, "
                f"proxy={item.get('proxy_ticker', '')}, "
                f"option={item.get('option_asymmetry', 'unavailable')}"
            )

    opportunities = context.opportunity_themes or {}
    if opportunities.get("items"):
        parts.append("[Opportunity themes]")
        parts.append(f"- {opportunities.get('summary', '')}")
        for item in opportunities.get("items", [])[:5]:
            parts.append(
                f"- {item.get('theme')}: {item.get('label')} "
                f"score={float(item.get('opportunity_score', 0.0)):.1f}; "
                f"{item.get('reason', '')}"
            )

    evaluation = context.evaluation or {}
    if evaluation:
        parts.append(
            f"- Market environment: {evaluation.get('status', 'unknown')} "
            f"(score={float(evaluation.get('score', 0.0)):.2f})"
        )
        for signal in evaluation.get("signals", [])[:8]:
            parts.append(
                f"  - {signal.get('name', 'signal')}: "
                f"{float(signal.get('score', 0.0)):.2f} "
                f"({signal.get('rationale', '')})"
            )

    ibd = context.ibd_regime or {}
    if ibd:
        parts.append("[IBD-style market regime]")
        parts.append(
            f"- Regime: {ibd.get('label', 'unknown')} "
            f"(score={float(ibd.get('score', 0.0)):.2f}, "
            f"exposure={ibd.get('exposure_level', 'unknown')})"
        )
        if ibd.get("rationale"):
            parts.append(f"- Regime rationale: {ibd['rationale']}")
        playbook = context.regime_playbook or {}
        if playbook:
            parts.append(
                f"- Current stance: {playbook.get('stance', '')} "
                f"Risk budget={playbook.get('risk_budget', '')}"
            )
            think_about = playbook.get("think_about") or []
            if think_about:
                parts.append("- Think about: " + "; ".join(think_about[:4]))

    micro = context.microstructure or {}
    if micro:
        parts.append(
            "- Microstructure: "
            f"VRP={_display_percent(micro.get('vrp'))}, "
            f"CTA={_nested(micro, 'cta_proxy', 'extremity')}, "
            f"liquidity={_nested(micro, 'liquidity', 'status')}, "
            f"unwind={micro.get('unwind_level', 'unknown')}"
        )
        if micro.get("narrative_text"):
            parts.append(str(micro["narrative_text"]))

    monitor = context.monitor or {}
    if monitor:
        dist_spy = monitor.get("distribution_spy", {})
        dist_ndx = monitor.get("distribution_ndx", {})
        climax = monitor.get("climax", {})
        spread = monitor.get("yield_spread", {})
        parts.append(
            "- Distribution days: "
            f"SPY={dist_spy.get('count', 0)} ({dist_spy.get('level', 'unknown')}), "
            f"NDX={dist_ndx.get('count', 0)} ({dist_ndx.get('level', 'unknown')})"
        )
        if climax.get("warnings"):
            parts.append("- Market climax warnings: " + "; ".join(climax["warnings"]))
        yield_10y = spread.get("yield_10y")
        yield_display = (
            f"{float(yield_10y):.2f}%" if yield_10y is not None else "unavailable"
        )
        parts.append(
            "- Yield spread: "
            f"{spread.get('overall_status', 'unknown')} (10Y={yield_display})"
        )

    if context.momentum:
        leaders = []
        for category, themes in context.momentum.items():
            top = themes[0] if themes else {}
            if top:
                leaders.append(
                    f"{category}: {top.get('theme')} {top.get('performance')}%"
                )
        if leaders:
            parts.append("- Momentum leaders: " + "; ".join(leaders[:4]))

    distortions = context.market_distortions or {}
    if distortions:
        parts.append("[Market distortions: fundamentals vs flows]")
        bullish = distortions.get("bullish") or []
        bearish = distortions.get("bearish") or []
        if bullish:
            parts.append(
                "- Bullish distortions: "
                + "; ".join(
                    f"{item.get('theme')} ({_ticker_list_text(item.get('tickers'))}) "
                    f"gap={float(item.get('distortion_score', 0.0)):.2f}"
                    for item in bullish[:5]
                )
            )
        if bearish:
            parts.append(
                "- Bearish distortions: "
                + "; ".join(
                    f"{item.get('theme')} ({_ticker_list_text(item.get('tickers'))}) "
                    f"gap={float(item.get('distortion_score', 0.0)):.2f}"
                    for item in bearish[:5]
                )
            )

    credit = context.credit_stress or {}
    if credit:
        parts.append("[Credit stress velocity]")
        parts.append(
            f"- Status: {credit.get('status_label', credit.get('status', 'unknown'))} "
            f"({credit.get('summary', '')})"
        )
        for item in (credit.get("indicators") or [])[:2]:
            parts.append(
                f"  - {item.get('label')}: "
                f"latest={float(item.get('latest', 0.0)):.2f}, "
                f"3m_delta={float(item.get('delta_3m', 0.0)):.2f}, "
                f"z={float(item.get('z_score', 0.0)):.2f}"
            )

    flow = context.flow_monitor or {}
    if flow:
        parts.append("[Leadership flow-pressure proxy]")
        parts.append(
            f"- Status: {flow.get('status', 'unknown')} ({flow.get('summary', '')})"
        )
        leaders = []
        for item in (flow.get("leaders") or [])[:3]:
            leaders.append(
                f"{item.get('label')} {item.get('ticker')} "
                f"score={float(item.get('leadership_score', 0.0)):.2f}"
            )
        if leaders:
            parts.append("  - Leaders: " + "; ".join(leaders))

    sector_flow = context.sector_flow or {}
    if sector_flow:
        parts.append("[Sector/theme flow]")
        if sector_flow.get("summary"):
            parts.append(f"- Flow summary: {sector_flow['summary']}")
        for market, payload in (sector_flow.get("markets") or {}).items():
            leaders = payload.get("leaders") or []
            if leaders:
                leader = leaders[0]
                parts.append(
                    f"- {market} leading flow: {leader.get('theme')} "
                    f"(score={float(leader.get('flow_score', 0.0)):.1f}, "
                    f"confidence={leader.get('confidence')}, "
                    f"continuation={leader.get('continuation')}, "
                    f"action={leader.get('action')})"
                )

    flow_alignment = context.flow_alignment or {}
    if flow_alignment:
        parts.append("[ETF proxy / sector-flow role split]")
        parts.append(f"- {flow_alignment.get('summary', '')}")
        parts.append(f"- ETF proxy role: {flow_alignment.get('etf_role', '')}")
        parts.append(f"- Sector/theme role: {flow_alignment.get('sector_role', '')}")

    japan = context.japan_conditions if context.market_type == "JP" else {}
    if japan:
        parts.append("[Nikkei upside six conditions]")
        parts.append(
            f"- Overall: {japan.get('summary', '')} "
            f"label={japan.get('score_label', 'unknown')}"
        )
        for item in (japan.get("items") or [])[:6]:
            parts.append(
                f"  - C{item.get('condition_no')}: {item.get('status_label')} "
                f"value={item.get('value')} evidence={item.get('evidence')}"
            )

    cross = context.cross_market if context.market_type == "JP" else {}
    if cross:
        parts.append(
            "[Cross-market stance] "
            f"{cross.get('stance', '')} "
            f"relative_flow={cross.get('relative_flow_score', 0)}"
        )

    return "\n".join(parts)
