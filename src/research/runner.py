"""Reuse the existing analysis services without invoking an AI provider."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.research.bundle import new_bundle, plain
from src.research.evidence import ResearchEvidence
from src.research.filing_catalog import issuer_links
from src.research.policy import synthesize


def capture(callback: Callable[[], Any]) -> Any:
    try:
        return plain(callback())
    except Exception as exc:
        # Provider exception text can contain URLs with credentials; do not persist it.
        return {
            "status": "unavailable",
            "error_type": type(exc).__name__,
            "warning": "処理失敗。診断とprovider healthを確認してください。",
        }


def stock(ticker: str, evidence: ResearchEvidence) -> dict:
    from src.services.equity_valuation_service import (
        _profile_key,
        build_equity_valuation,
    )
    from src.services.stock_dashboard_service import build_stock_dashboard_context
    from src.services.stock_trade_analysis_service import build_stock_trade_analysis

    context = build_stock_dashboard_context(ticker)
    return {
        "analysis": plain(context),
        "valuation": build_equity_valuation(
            context.info, profile=_profile_key(context.info)
        ),
        "entry_reference": build_stock_trade_analysis(context.stock_signal_context),
        "filings": evidence.for_ticker(ticker),
        "filing_catalog": issuer_links(ticker, context.info),
        "filing_valuation": next(
            (item.calculate() for item in evidence.valuations if item.ticker == ticker),
            {"status": "unavailable", "reason": "No source-linked valuation inputs"},
        ),
        "filing_valuations": valuation_results(evidence, ticker, plain(context)),
        "horizon": "6 months to 2 years; daily Entry is a separate timing reference",
    }


def valuation_results(
    evidence: ResearchEvidence, ticker: str, analysis: dict
) -> list[dict]:
    rows = analysis.get("chart_data", [])
    latest = next(
        (r for r in reversed(rows) if r.get("price") is not None and r.get("name")), {}
    )
    return [
        {
            **item.calculate(),
            "reverse_dcf": item.reverse_dcf(latest.get("price"), latest.get("name")),
        }
        for item in evidence.valuations
        if item.ticker == ticker
    ]


def market(market_type: str, allow_options: bool, scan_fomo: bool = False) -> dict:
    from src.services.market_dashboard_service import (
        build_market_high_context,
        build_market_options_context,
        build_market_summary_context,
        build_market_theme_flow_context,
        build_market_volatility_sentiment_context,
    )

    context = build_market_summary_context(market_type)
    context = build_market_theme_flow_context(market_type, context)
    context = build_market_high_context(market_type, context)
    context = build_market_volatility_sentiment_context(market_type, context)
    if allow_options and market_type == "US":
        context = build_market_options_context(market_type, context)
    analysis = plain(context)
    if scan_fomo:
        from src.services.market_dashboard_service import build_fomo_scan_context

        analysis["fomo_scan"] = capture(build_fomo_scan_context)
        analysis["fomo_scan_scope"] = "Existing US universe; not a Japan-wide scan"
    sanitize_market_conditions(analysis)
    return {
        "analysis": analysis,
        "options_request": "authorized"
        if allow_options and market_type == "US"
        else "not_requested",
        "option_warning": "JPオプションは未対応。USの追加取得は明示指定時のみ。",
    }


def sanitize_market_conditions(analysis: dict) -> None:
    """The same condition/proxy contract applies to full and staged acquisition."""
    japan = analysis.get("japan_conditions", {})
    if japan:
        # Preserve individual observations, not a missing-as-zero aggregate.
        for key in ("score", "score_label", "summary"):
            japan.pop(key, None)
        japan["summary"] = (
            "条件別の直接観測・代理指標・未確認を区別。総合点は使用しません。"
        )
        for item in japan.get("items", []):
            item.pop("score", None)
            if (
                item.get("condition_no") in {5, 6}
                and item.get("source_type") == "proxy"
            ):
                item["proxy_observation"] = item.get("value")
                item["status"] = "unavailable"
                item["assessment"] = (
                    "価格・テーマ代理指標からEPS改定や海外投資家実フローは確認できません。"
                )


def theme(market_type: str, evidence: ResearchEvidence | None = None) -> dict:
    from src.services.theme_leader_service import build_evidence_theme_leaders
    from src.services.trend_ranking_service import build_trend_ranking_context

    leaders = plain(
        build_evidence_theme_leaders(
            market_type, (evidence or ResearchEvidence()).discovery
        )
    )
    # The legacy service shares a typed contract with Gemini discovery. The Codex
    # packet names its actual evidence input, without pretending a model ran.
    data = leaders.get("data", {})
    for key in list(data):
        if key.startswith("gemini_"):
            data["external_evidence_" + key.removeprefix("gemini_")] = data.pop(key)
    for item in data.get("excluded", []):
        if isinstance(item, dict) and isinstance(item.get("reason"), str):
            item["reason"] = item["reason"].replace("Gemini未検証", "外部資料未検証")
    return {
        "ranking": build_trend_ranking_context(
            market_type, include_options=False, top_n=100
        ),
        "leaders": leaders,
        "external_discovery": {
            "status": "input_supplied"
            if evidence and evidence.external_candidates
            else "not_supplied",
        },
    }


def diagnostics() -> dict:
    from src.services.data_fetch_manifest import get_data_fetch_manifest
    from src.services.provider_health import load_provider_health

    return {
        "provider_health": plain(load_provider_health()),
        "legacy_fetch_manifest": get_data_fetch_manifest(),
        "network_requested": False,
        "migration": "Codex offline dashboard; legacy runtime retained pending full parity acceptance",
    }


def run(
    workflow: str,
    *,
    market_type: str = "US",
    ticker: str = "",
    allow_options: bool = False,
    scan_fomo: bool = False,
    evidence: ResearchEvidence | None = None,
    profile: str = "standard",
) -> dict:
    if profile not in {"standard", "advanced"}:
        raise ValueError("Unsupported acquisition profile")
    if profile == "standard" and (allow_options or scan_fomo):
        raise ValueError(
            "Optional acquisitions require advanced and explicit permission"
        )
    if workflow not in {
        "overview",
        "market",
        "stock",
        "theme",
        "policy",
        "diagnostics",
    }:
        raise ValueError("Unknown workflow")
    if market_type not in {"US", "JP"}:
        raise ValueError("Unsupported market")
    if allow_options and (market_type != "US" or workflow not in {"market", "policy"}):
        raise ValueError("Options require an explicit US market or policy run")
    if scan_fomo and (market_type != "US" or workflow not in {"market", "policy"}):
        raise ValueError("FOMO scan requires an explicit US market or policy run")
    ticker = ticker.strip().upper()
    if workflow == "stock" and not ticker:
        raise ValueError("stock requires a ticker")
    evidence = evidence or ResearchEvidence()
    if profile == "standard" and workflow in {"overview", "market", "theme", "policy"}:
        from src.research.standard import standard_sections

        sections = standard_sections(
            ("US", "JP") if workflow == "overview" else (market_type,)
        )
        if workflow != "overview":
            sections = {
                "market": sections["markets"][market_type],
                "theme": sections["themes"][market_type],
                "policy": sections["policies"][market_type],
                "comparisons": sections["comparisons"],
            }
        return new_bundle(
            workflow,
            {
                "market": market_type,
                "profile": profile,
                "ticker": ticker,
                "allow_options": False,
                "scan_fomo": False,
                "evidence": evidence.model_dump(mode="json"),
            },
            sections,
        )
    sections = {}
    if workflow == "overview":
        from concurrent.futures import ThreadPoolExecutor

        from src.research.comparison import fetch_comparisons

        def overview_market(selected):
            return capture(lambda: market(selected, False))

        with ThreadPoolExecutor(max_workers=2) as pool:
            sections["markets"] = dict(
                zip(("US", "JP"), pool.map(overview_market, ("US", "JP")), strict=True)
            )
        sections["themes"] = {
            key: {"ranking": packet.get("analysis", {}).get("trend_ranking", {})}
            for key, packet in sections["markets"].items()
        }
        sections["comparisons"] = capture(fetch_comparisons)
    if workflow in {"market", "policy"}:
        sections["market"] = capture(
            lambda: market(market_type, allow_options, scan_fomo)
        )
    if workflow in {"theme", "policy"}:
        sections["theme"] = capture(lambda: theme(market_type, evidence))
    if workflow == "stock":
        sections[ticker] = capture(lambda: stock(ticker, evidence))
    if workflow == "policy":
        leaders = sections.get("theme", {}).get("leaders", {}).get("data", {})
        for candidate in leaders.get("candidates", [])[:5]:
            symbol = candidate["ticker"]
            sections[symbol] = capture(lambda symbol=symbol: stock(symbol, evidence))
        sections["policy"] = synthesize(sections, market_type)
    if workflow == "diagnostics":
        sections["diagnostics"] = capture(diagnostics)
    return new_bundle(
        workflow,
        {
            "market": market_type,
            "profile": profile,
            "ticker": ticker,
            "allow_options": allow_options,
            "scan_fomo": scan_fomo,
            "evidence": evidence.model_dump(mode="json"),
        },
        sections,
    )


def resume(bundle: dict, evidence: ResearchEvidence) -> dict:
    """Apply new filing evidence and recalculate without any provider/model request."""
    from copy import deepcopy

    from src.research.bundle import validate_bundle

    original = validate_bundle(bundle)
    sections = deepcopy(original["sections"])
    reserved = {
        "market",
        "markets",
        "theme",
        "themes",
        "policy",
        "policies",
        "comparisons",
        "diagnostics",
    }
    quarter_only = bool(evidence.quarterly_records) and not any(
        (
            evidence.financial_histories,
            evidence.valuations,
            evidence.accounting_reviews,
            evidence.claims,
        )
    )
    for ticker, packet in sections.items():
        if ticker in reserved:
            continue
        if quarter_only:
            from src.research.quarterly import evaluate_quarters

            records = [
                r.model_dump(mode="json")
                for r in evidence.quarterly_records
                if r.ticker == ticker
            ]
            if records:
                packet.setdefault("filings", {})["quarterly_records"] = records
                packet["quarterly_fundamentals"] = evaluate_quarters(records)
                packet["quarterly_fundamentals"]["sources"] = [
                    s.model_dump(mode="json")
                    for s in evidence.sources
                    if s.ticker == ticker
                ]
            continue  # A quarter review must not erase unrelated saved valuation/accounting.
        packet["filings"] = evidence.for_ticker(ticker)
        packet["filing_valuation"] = next(
            (item.calculate() for item in evidence.valuations if item.ticker == ticker),
            {"status": "unavailable", "reason": "No source-linked valuation inputs"},
        )
        packet["filing_valuations"] = valuation_results(
            evidence, ticker, packet.get("analysis", {})
        )
    if (
        original["workflow"] == "policy"
        and original["inputs"].get("profile") != "standard"
    ):
        sections["policy"] = synthesize(
            sections, original["inputs"].get("market", "US")
        )
    if evidence.quarterly_records:
        from src.research.quarterly import evaluate_quarters

        for packet in [
            sections.get("market", {}),
            *sections.get("markets", {}).values(),
        ]:
            analysis = packet.get("analysis", {})
            screening = {
                r["ticker"]: r for r in analysis.get("topdown", {}).get("screening", [])
            }
            for ticker in {r.ticker for r in evidence.quarterly_records}:
                if ticker not in screening:
                    continue
                records = [
                    r.model_dump(mode="json")
                    for r in evidence.quarterly_records
                    if r.ticker == ticker
                ]
                result = evaluate_quarters(
                    records, screening[ticker].get("profile", "general")
                )
                result.update(
                    ticker=ticker,
                    sources=[
                        s.model_dump(mode="json")
                        for s in evidence.sources
                        if s.ticker == ticker
                    ],
                )
                analysis.setdefault("quarterly_fundamentals", {})[ticker] = result
    updated = new_bundle(
        original["workflow"],
        {**original["inputs"], "evidence": evidence.model_dump(mode="json")},
        sections,
    )
    updated["resumed_from"] = {
        "run_id": original["run_id"],
        "created_at": original["created_at"],
        "network_requested": False,
    }
    updated["warnings"].append(
        "保存入力の再計算。価格・市場・候補の再取得は行っていません。外部候補の追加は新規theme実行で行います。"
    )
    apply_interpretations(updated, evidence, original)
    return updated


def apply_interpretations(
    updated: dict, evidence: ResearchEvidence, original: dict
) -> None:
    for interpretation in evidence.interpretations:
        if interpretation.run_id != original["run_id"]:
            raise ValueError("Interpretation must reference the original run")
        for path in interpretation.input_paths:
            node = original
            keys = (
                [
                    key.replace("~1", "/").replace("~0", "~")
                    for key in path[1:].split("/")
                ]
                if path.startswith("/")
                else path.split(".")
            )
            for key in keys:
                if not isinstance(node, dict) or key not in node:
                    raise ValueError("Interpretation references a missing calculation")
                node = node[key]
    updated["interpretations"] = [
        item.model_dump(mode="json") for item in evidence.interpretations
    ]


def refresh(
    bundle: dict, stage: str, *, market_type: str, allow_options: bool = False
) -> dict:
    """Refresh one acquisition stage, preserving unrelated saved results."""
    from copy import deepcopy

    from src.research.bundle import validate_bundle
    from src.services import market_dashboard_service as service
    from src.services.analysis_context import MarketContext

    stages = {
        "summary": service.build_market_summary_context,
        "theme-flow": service.build_market_theme_flow_context,
        "credit-risk": service.build_market_high_context,
        "vol-sentiment": service.build_market_volatility_sentiment_context,
        "options": service.build_market_options_context,
    }
    if stage not in stages or market_type not in {"US", "JP"}:
        raise ValueError("Invalid refresh stage/market")
    if stage == "options" and (market_type != "US" or not allow_options):
        raise ValueError("Options stage requires explicit US authorization")
    if allow_options and stage != "options":
        raise ValueError("Options permission only belongs to options stage")
    original = validate_bundle(bundle)
    sections = deepcopy(original["sections"])
    if "markets" in sections:
        old_packet = sections["markets"].get(market_type, {})
    else:
        if original["inputs"]["market"] != market_type:
            raise ValueError("Refresh cannot mix markets")
        old_packet = sections.get("market", {})
    base = MarketContext.from_mapping(
        {**old_packet.get("analysis", {}), "market_type": market_type}
    )
    # Services copy base.errors. Isolate this attempt, including repeated failures.
    previous_errors = list(base.errors)
    base.errors = []
    result = capture(
        lambda: (
            stages[stage](market_type)
            if stage == "summary"
            else stages[stage](market_type, base)
        )
    )
    packet = deepcopy(old_packet)
    if not result.get("error_type") and result.get("errors"):
        packet["attempted_analysis"] = result
        result = {
            "status": "partial",
            "error_type": "StagePartialFailure",
            "warning": "段階更新で取得失敗。前回の結果と今回の試行を分離して保存。",
        }
    if result.get("error_type"):
        packet["refresh_failure"] = {
            "stage": stage,
            **result,
            "previous_result_retained": True,
        }
    else:
        if stage == "summary":
            analysis = deepcopy(old_packet.get("analysis", {}))
            for key in (
                "market_data",
                "market_charts",
                "market_config",
                "fetched_at",
            ):
                if key in result:
                    analysis[key] = result[key]
            for key, identity in (("data_status", "name"), ("provenance", "item_id")):
                merged = {row[identity]: row for row in analysis.get(key, [])}
                merged.update({row[identity]: row for row in result.get(key, [])})
                analysis[key] = list(merged.values())
            packet["analysis"] = analysis
        else:
            packet["analysis"] = result
            packet["analysis"]["errors"] = previous_errors
        packet.pop("refresh_failure", None)
        packet.pop("attempted_analysis", None)
        sanitize_market_conditions(packet["analysis"])
    packet["refreshed_stage"] = stage
    if "markets" in sections:
        sections["markets"][market_type] = packet
        if "themes" in sections and not result.get("error_type") and stage != "summary":
            sections["themes"][market_type] = {
                **sections["themes"].get(market_type, {}),
                "ranking": packet["analysis"].get("trend_ranking", {}),
            }
    else:
        sections["market"] = packet
    if original["workflow"] == "policy":
        sections["policy"] = synthesize(sections, market_type)
    updated = new_bundle(
        original["workflow"],
        {**original["inputs"], "refresh_stage": stage, "profile": "advanced"},
        sections,
    )
    updated["refreshed_from"] = {
        "run_id": original["run_id"],
        "stage": stage,
        "market": market_type,
    }
    if result.get("error_type"):
        updated["execution_status"] = "partial"
    return updated
