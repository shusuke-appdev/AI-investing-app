"""Integrated sector/theme trend ranking with optional ETF option context."""

from __future__ import annotations

from typing import Any

from src.log_config import get_logger
from src.option_analyst import analyze_option_sentiment
from src.theme_analyst import get_ranked_themes
from src.theme_taxonomy import get_theme_profile
from src.themes_config import get_themes

logger = get_logger(__name__)

RANKING_PERIODS = ("1週間", "1ヶ月", "6ヶ月")
MAX_OPTION_PROXIES = 6


def build_trend_ranking_context(
    market_type: str = "US",
    *,
    sector_flow: dict[str, Any] | None = None,
    distortions: dict[str, Any] | None = None,
    include_options: bool = False,
    top_n: int = 10,
) -> dict[str, Any]:
    """Build the app's unified trend ranking for one market."""

    period_maps = _period_rank_maps(market_type)
    if not period_maps:
        return {
            "market": market_type,
            "items": [],
            "summary": "トレンドランキングを算出できません。",
            "quality_warnings": ["Theme performance data is unavailable."],
        }

    base_rows = _base_rows(market_type, period_maps, sector_flow, distortions)
    option_map = (
        _option_asymmetry_map(base_rows[:MAX_OPTION_PROXIES])
        if include_options and market_type == "US"
        else {}
    )
    rows = []
    for row in base_rows:
        option_payload = option_map.get(row["option_proxy_ticker"], {})
        rows.append(_finalize_row(row, option_payload))

    rows.sort(key=lambda item: item["total_score"], reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
        row["rank_points"] = _rank_points(idx)

    visible = rows[:top_n]
    return {
        "market": market_type,
        "items": visible,
        "summary": _summary(visible, include_options),
        "quality_warnings": _ranking_warnings(period_maps, option_map, include_options),
        "option_updated": include_options,
    }


def find_theme_rankings(
    market_type: str,
    themes: list[str],
    *,
    include_options: bool = False,
) -> dict[str, Any]:
    """Return ranking rows for selected themes, used by stock analysis."""

    ranking = build_trend_ranking_context(
        market_type,
        include_options=include_options and market_type == "US",
        top_n=50,
    )
    lookup = {str(item.get("theme")): item for item in ranking.get("items", [])}
    selected = [lookup[theme] for theme in themes if theme in lookup]
    selected.sort(key=lambda item: int(item.get("rank") or 999))
    best = selected[0] if selected else {}
    return {
        "items": selected,
        "best_rank": best.get("rank"),
        "best_theme": best.get("theme", ""),
        "best_total_score": best.get("total_score"),
        "best_rank_points": best.get("rank_points", 0),
        "summary": _stock_summary(best)
        if best
        else "該当テーマは統合ランキング圏外です。",
        "quality_warnings": ranking.get("quality_warnings", []),
    }


def build_opportunity_themes(
    trend_ranking: dict[str, Any] | None,
    *,
    market_distortions: dict[str, Any] | None = None,
    max_items: int = 5,
) -> dict[str, Any]:
    """Select themes with favorable trend, asymmetry, and distortion evidence."""

    ranking = trend_ranking or {}
    distortions = _distortion_lookup(market_distortions)
    rows = []
    for item in ranking.get("items", []):
        score = float(item.get("total_score", 0.0))
        option_score = float(item.get("option_score", 0.0))
        distortion = distortions.get(str(item.get("theme")), {})
        distortion_score = float(distortion.get("distortion_score") or 0.0)
        opportunity_score = score + option_score * 0.8 + max(distortion_score, 0) * 30
        if opportunity_score < 20:
            continue
        rows.append(
            {
                "theme": item.get("theme", ""),
                "parent_sector": item.get("parent_sector", ""),
                "rank": item.get("rank", 0),
                "opportunity_score": round(opportunity_score, 1),
                "label": _opportunity_label(opportunity_score, option_score),
                "reason": _opportunity_reason(item, distortion),
                "representative_tickers": item.get("representative_tickers", []),
                "option_asymmetry": item.get("option_asymmetry", "unavailable"),
                "invalidation": _invalidation(item),
            }
        )
    rows.sort(key=lambda row: row["opportunity_score"], reverse=True)
    return {
        "items": rows[:max_items],
        "summary": _opportunity_summary(rows),
    }


def _period_rank_maps(market_type: str) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for period in RANKING_PERIODS:
        try:
            ranked = get_ranked_themes(period, market_type)
        except Exception as exc:
            logger.warning(
                "[TrendRanking] %s %s ranking failed: %s", market_type, period, exc
            )
            result[period] = {}
            continue
        result[period] = {str(item.get("theme")): dict(item) for item in ranked}
    return result


def _base_rows(
    market_type: str,
    period_maps: dict[str, dict[str, dict[str, Any]]],
    sector_flow: dict[str, Any] | None,
    distortions: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    flow_lookup = _flow_lookup(sector_flow, market_type)
    distortion_lookup = _distortion_lookup(distortions)
    rows = []
    for theme, tickers in get_themes(market_type).items():
        profile = get_theme_profile(theme, market_type, tickers=tickers)
        perf_1w = _performance(period_maps, "1週間", theme)
        perf_1m = _performance(period_maps, "1ヶ月", theme)
        perf_6m = _performance(period_maps, "6ヶ月", theme)
        if perf_1w is None and perf_1m is None and perf_6m is None:
            continue
        flow = flow_lookup.get(theme, {})
        distortion = distortion_lookup.get(theme, {})
        base_score = _base_score(perf_1w, perf_1m, perf_6m, flow, distortion)
        rows.append(
            {
                "theme": theme,
                "market": market_type,
                "parent_sector": profile.parent_sector,
                "proxy_ticker": profile.proxy_ticker,
                "option_proxy_ticker": profile.option_proxy_ticker,
                "representative_tickers": list(profile.representative_tickers),
                "performance_1w": _round(perf_1w),
                "performance_1m": _round(perf_1m),
                "performance_6m": _round(perf_6m),
                "flow_score": _round(flow.get("flow_score")),
                "flow_confidence": str(flow.get("confidence") or ""),
                "participation": _round(flow.get("participation")),
                "distortion_score": _round(distortion.get("distortion_score")),
                "base_score": round(base_score, 1),
            }
        )
    rows.sort(key=lambda item: item["base_score"], reverse=True)
    return rows


def _option_asymmetry_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        proxy = str(row.get("option_proxy_ticker") or "").upper()
        if not proxy or proxy in result:
            continue
        try:
            analysis = analyze_option_sentiment(proxy, allow_marketdata=True)
        except Exception as exc:
            logger.warning("[TrendRanking] Option proxy %s failed: %s", proxy, exc)
            analysis = None
        result[proxy] = _option_payload(proxy, analysis)
    return result


def _option_payload(proxy: str, analysis: dict[str, Any] | None) -> dict[str, Any]:
    if not analysis:
        return {
            "option_proxy_ticker": proxy,
            "option_asymmetry": "unavailable",
            "option_score": 0.0,
            "option_summary": "テーマETFオプションは取得できません。",
        }
    gex = analysis.get("gex") or {}
    nearby_gex = _float(gex.get("nearby_net_gex"))
    skew = _float(analysis.get("skew"))
    pcr = (analysis.get("pcr") or {}).get("volume_pcr")
    label = "pinning"
    score = 0.0
    if nearby_gex is not None and nearby_gex < 0 and (skew is None or skew <= 0.05):
        label = "upside_squeeze_candidate"
        score = 12.0
    elif nearby_gex is not None and nearby_gex < 0 and skew and skew > 0.05:
        label = "downside_vol_expansion"
        score = -12.0
    elif nearby_gex is not None and nearby_gex > 0:
        label = "pinning_resistance"
        score = -3.0
    if pcr is not None and float(pcr) < 0.75:
        score += 4.0
    elif pcr is not None and float(pcr) > 1.25:
        score -= 4.0
    return {
        "option_proxy_ticker": proxy,
        "option_asymmetry": label,
        "option_score": round(score, 1),
        "option_summary": _option_summary(label, analysis),
        "option_source": analysis.get("source", ""),
        "option_data_as_of": analysis.get("data_as_of", ""),
        "option_data_quality": analysis.get("data_quality", ""),
        "option_credits_consumed": analysis.get("credits_consumed"),
        "option_credits_remaining": analysis.get("credits_remaining"),
        "quality_warnings": analysis.get("quality_warnings", []),
    }


def _finalize_row(
    row: dict[str, Any], option_payload: dict[str, Any]
) -> dict[str, Any]:
    option_score = float(option_payload.get("option_score", 0.0))
    total = float(row["base_score"]) + option_score
    return {
        **row,
        **option_payload,
        "option_score": round(option_score, 1),
        "total_score": round(total, 1),
        "current_score": round(float(row["base_score"]) + option_score * 0.4, 1),
        "one_week_score": round(
            _score_part(row.get("performance_1w"), 1.8) + option_score, 1
        ),
        "one_month_score": round(
            _score_part(row.get("performance_1m"), 1.2)
            + _score_part(row.get("performance_6m"), 0.35)
            + option_score * 0.5,
            1,
        ),
    }


def _base_score(
    perf_1w: float | None,
    perf_1m: float | None,
    perf_6m: float | None,
    flow: dict[str, Any],
    distortion: dict[str, Any],
) -> float:
    score = (
        _score_part(perf_1w, 1.6)
        + _score_part(perf_1m, 1.1)
        + _score_part(perf_6m, 0.25)
    )
    score += _score_part(flow.get("flow_score"), 0.18)
    score += _score_part(flow.get("participation"), 15.0)
    distortion_score = _float(distortion.get("distortion_score"))
    if distortion_score is not None and distortion_score > 0:
        score += distortion_score * 20.0
    return score


def _flow_lookup(
    sector_flow: dict[str, Any] | None, market_type: str
) -> dict[str, dict[str, Any]]:
    payload = ((sector_flow or {}).get("markets") or {}).get(market_type, {})
    return {str(item.get("theme")): item for item in payload.get("leaders", [])}


def _distortion_lookup(
    distortions: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    result = {}
    for key in ("bullish", "bearish", "all"):
        for item in (distortions or {}).get(key, []) or []:
            theme = str(item.get("theme") or "")
            if theme:
                result[theme] = item
    return result


def _performance(
    period_maps: dict[str, dict[str, dict[str, Any]]], period: str, theme: str
) -> float | None:
    return _float((period_maps.get(period) or {}).get(theme, {}).get("performance"))


def _score_part(value: Any, weight: float) -> float:
    number = _float(value)
    return 0.0 if number is None else number * weight


def _rank_points(rank: int) -> int:
    if rank <= 3:
        return 10
    if rank <= 10:
        return 6
    if rank <= 20:
        return 3
    return 0


def _opportunity_label(score: float, option_score: float) -> str:
    if score >= 50 and option_score > 0:
        return "投資妙味/上方向非対称"
    if score >= 40:
        return "上昇候補"
    if score >= 25:
        return "押し目待ち"
    return "観察"


def _opportunity_reason(item: dict[str, Any], distortion: dict[str, Any]) -> str:
    parts = [f"統合順位 {item.get('rank')}位"]
    if item.get("option_asymmetry") not in ("", "unavailable", None):
        parts.append(f"オプション={item.get('option_asymmetry')}")
    if distortion.get("classification"):
        parts.append(f"歪み={distortion.get('classification')}")
    return " / ".join(parts)


def _invalidation(item: dict[str, Any]) -> str:
    proxy = item.get("proxy_ticker") or item.get("representative_tickers", [""])[0]
    return f"{proxy}の50日線割れ、またはランキング20位以下への低下"


def _summary(rows: list[dict[str, Any]], include_options: bool) -> str:
    if not rows:
        return "統合トレンドランキングを算出できません。"
    suffix = "MarketDataオプションを反映" if include_options else "価格/フロー中心"
    return f"首位は {rows[0]['theme']}（{suffix}）。"


def _stock_summary(best: dict[str, Any]) -> str:
    return (
        f"{best.get('theme')} は統合トレンドランキング "
        f"{best.get('rank')}位、順位ポイント {best.get('rank_points', 0)}。"
    )


def _opportunity_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "注目テーマ候補はまだ抽出できません。"
    return f"注目候補は {rows[0]['theme']} を筆頭に {len(rows)}件。"


def _ranking_warnings(
    period_maps: dict[str, dict[str, dict[str, Any]]],
    option_map: dict[str, dict[str, Any]],
    include_options: bool,
) -> list[str]:
    warnings = [
        f"{period} ranking unavailable."
        for period, payload in period_maps.items()
        if not payload
    ]
    if include_options:
        for proxy, payload in option_map.items():
            for warning in payload.get("quality_warnings", []):
                warnings.append(f"{proxy}: {warning}")
    return warnings[:10]


def _option_summary(label: str, analysis: dict[str, Any]) -> str:
    source = analysis.get("source", "")
    text = {
        "upside_squeeze_candidate": "負の近傍GEXと過度でない下方Skewで上方向ボラ拡大候補。",
        "downside_vol_expansion": "負の近傍GEXと下方Skewで下方向ボラ拡大に警戒。",
        "pinning_resistance": "正の近傍GEXでピン留め/抵抗を優先。",
        "pinning": "オプション構造は中立寄り。",
    }.get(label, "オプション構造は判定不能。")
    return f"{text} source={source or 'unknown'}"


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any) -> float | None:
    number = _float(value)
    return round(number, 2) if number is not None else None
