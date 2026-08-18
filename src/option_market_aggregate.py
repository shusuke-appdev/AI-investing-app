"""Cross-index option aggregation and completeness reporting."""

from typing import Any

import pandas as pd

from src import option_analyst as _option_analyst
from src.option_analyst import (
    OPTION_HORIZON_SPECS,
    _build_term_structure,
    _float_or_none,
    _unique_warnings,
    analyze_option_sentiment,
    logger,
)


def _sync_compat_dependencies() -> None:
    """Honor analysis patches applied through the historical module facade."""

    global analyze_option_sentiment
    analyze_option_sentiment = _option_analyst.analyze_option_sentiment


def get_major_indices_options(market_type: str = "US") -> list[dict]:
    """
    主要指数ETF (SPY, QQQ, IWM) のオプション分析を取得します。
    日本市場ではオプションデータが取得できないため空リストを返します。

    Args:
        market_type: "US" または "JP"

    Returns:
        各指数のオプション分析結果のリスト（日本市場では空）
    """
    _sync_compat_dependencies()
    if market_type == "JP":
        return []

    indices = ["SPY", "QQQ", "IWM"]
    results = []
    failed_tickers = []

    for ticker in indices:
        try:
            analysis = analyze_option_sentiment(ticker)
            if analysis:
                results.append(analysis)
            else:
                failed_tickers.append(ticker)
                logger.warning(
                    f"[OptionAnalyst] analyze_option_sentiment returned None for {ticker}"
                )
        except Exception as e:
            failed_tickers.append(ticker)
            logger.error(f"[OptionAnalyst] Exception analyzing {ticker}: {e}")

    if failed_tickers:
        logger.warning(f"[OptionAnalyst] Failed tickers: {failed_tickers}")

    return results


def get_major_indices_option_status(market_type: str = "US") -> dict:
    """Return option analyses plus retrieval status for UI and AI context."""

    _sync_compat_dependencies()
    if market_type == "JP":
        return {
            "items": [],
            "status": "not_applicable",
            "failed_tickers": [],
            "error_message": "Option data is not available for JP market monitoring.",
            "source": "not_applicable",
            "fetched_at": "",
            "is_stale": False,
            "cache_status": "not_applicable",
            "cache_age_seconds": None,
            "quality_warnings": [],
            "provider_active": False,
            "fallback_reason": "",
            "gamma_coverage": None,
            "complete_status": "not_applicable",
            "horizons": [],
            "term_structure": {},
        }

    indices = ["SPY", "QQQ", "IWM"]
    results = []
    failed_tickers = []

    for ticker in indices:
        try:
            analysis = analyze_option_sentiment(ticker, allow_marketdata=True)
            if analysis:
                results.append(analysis)
            else:
                failed_tickers.append(ticker)
                logger.warning(
                    f"[OptionAnalyst] analyze_option_sentiment returned None for {ticker}"
                )
        except Exception as exc:
            failed_tickers.append(ticker)
            logger.error(f"[OptionAnalyst] Exception analyzing {ticker}: {exc}")

    if failed_tickers:
        logger.warning(f"[OptionAnalyst] Failed tickers: {failed_tickers}")

    quality_warnings = _aggregate_quality_warnings(results)
    non_available = [
        item.get("ticker", "")
        for item in results
        if item.get("data_quality") not in ("available", None)
    ]
    if results and failed_tickers:
        status = "partial"
        error_message = "Option data partially unavailable: " + ", ".join(
            failed_tickers
        )
    elif results and non_available:
        status = "partial"
        error_message = "Option data has quality limitations: " + ", ".join(
            ticker for ticker in non_available if ticker
        )
    elif results:
        status = "available"
        error_message = ""
    else:
        status = "failed"
        error_message = "Option data unavailable for SPY, QQQ, and IWM."

    return {
        "items": results,
        "status": status,
        "failed_tickers": failed_tickers,
        "error_message": error_message,
        "source": _aggregate_sources(results),
        "fetched_at": _latest_fetched_at(results),
        "is_stale": any(bool(item.get("is_stale")) for item in results),
        "cache_status": _aggregate_cache_status(results),
        "cache_age_seconds": _max_cache_age_seconds(results),
        "quality_warnings": quality_warnings,
        "data_as_of": _latest_value(results, "data_as_of"),
        "data_mode": _aggregate_data_modes(results),
        "resolved_expiration": _latest_value(results, "resolved_expiration"),
        "resolved_dte": _min_optional_values(results, "resolved_dte"),
        "expiration_policy": _aggregate_value_set(results, "expiration_policy"),
        "expiration_fallback_reason": _first_value(
            results, "expiration_fallback_reason"
        ),
        "credits_consumed": _sum_optional_values(results, "credits_consumed"),
        "credits_remaining": _min_optional_values(results, "credits_remaining"),
        "provider_active": any(bool(item.get("provider_active")) for item in results),
        "fallback_reason": _first_value(results, "fallback_reason"),
        "gamma_coverage": _aggregate_gamma_coverage(results),
        "complete_status": _aggregate_complete_status(results, status),
        "horizons": _aggregate_option_horizons(results),
        "term_structure": _aggregate_term_structure(results),
    }


def _complete_status(
    *,
    provider_active: bool,
    gex: dict | None,
    quality: str,
    is_stale: bool,
    fallback_reason: str,
    gamma_coverage_value: float,
) -> str:
    if fallback_reason:
        return "fallback"
    if not provider_active:
        return "provider_inactive"
    if is_stale:
        return "stale_cache"
    if gamma_coverage_value < 1.0:
        return "partial_greeks"
    if gex is None:
        return "gex_unavailable"
    if quality == "available":
        return "complete"
    return quality or "partial"


def _aggregate_quality_warnings(results: list[dict]) -> list[str]:
    warnings = []
    for item in results:
        for warning in item.get("quality_warnings", []):
            warnings.append(f"{item.get('ticker', '')}: {warning}")
    return _unique_warnings(warnings)


def _aggregate_option_horizons(results: list[dict]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in results:
        ticker = str(item.get("ticker") or "")
        for horizon in item.get("horizons", []) or []:
            key = str(horizon.get("key") or "")
            if not key:
                continue
            bucket = buckets.setdefault(
                key,
                {
                    "key": key,
                    "label": str(horizon.get("label") or key),
                    "target_dte": horizon.get("target_dte"),
                    "tickers": [],
                    "fresh_tickers": [],
                    "stale_tickers": [],
                    "iv_values": [],
                    "expected_move_values": [],
                    "pcr_values": [],
                    "skew_by_ticker": {},
                    "gex_values": [],
                    "gamma_values": [],
                    "sources": set(),
                    "warnings": [],
                    "resolved_expirations": [],
                    "dte_values": [],
                },
            )
            if ticker:
                bucket["tickers"].append(ticker)
            is_stale = bool(horizon.get("is_stale") or item.get("is_stale"))
            if ticker:
                bucket["stale_tickers" if is_stale else "fresh_tickers"].append(ticker)
            if is_stale:
                bucket["warnings"].append(
                    f"{ticker or 'Option data'} is stale and excluded from strategy metrics."
                )
            else:
                _append_number(bucket["iv_values"], horizon.get("iv"))
                _append_number(
                    bucket["expected_move_values"], horizon.get("expected_move_pct")
                )
                _append_number(
                    bucket["pcr_values"],
                    (horizon.get("pcr") or {}).get("volume_pcr"),
                )
                _append_number(
                    bucket["gex_values"],
                    (horizon.get("gex") or {}).get("nearby_net_gex"),
                )
                _append_number(bucket["gamma_values"], horizon.get("gamma_coverage"))
            skew_entry = _skew_entry(ticker, item, horizon)
            if ticker and skew_entry is not None:
                bucket["skew_by_ticker"][ticker] = skew_entry
                bucket["warnings"].extend(skew_entry.get("warnings") or [])
            _append_number(bucket["dte_values"], horizon.get("dte"))
            if horizon.get("source"):
                bucket["sources"].add(str(horizon.get("source")))
            if horizon.get("resolved_expiration"):
                bucket["resolved_expirations"].append(
                    str(horizon.get("resolved_expiration"))
                )
            bucket["warnings"].extend(list(horizon.get("quality_warnings") or []))

    ordered = []
    order = {str(spec["key"]): idx for idx, spec in enumerate(OPTION_HORIZON_SPECS)}
    for key, bucket in sorted(buckets.items(), key=lambda item: order.get(item[0], 99)):
        iv = _avg(bucket["iv_values"])
        expected_move = _avg(bucket["expected_move_values"])
        pcr = _avg(bucket["pcr_values"])
        skew_by_ticker = dict(sorted(bucket["skew_by_ticker"].items()))
        skew_reference = _spy_skew_reference(skew_by_ticker)
        skew = _float_or_none((skew_reference or {}).get("value"))
        skew_dispersion = _direct_skew_dispersion(skew_by_ticker)
        nearby_gex = _avg(bucket["gex_values"])
        gamma = _avg(bucket["gamma_values"])
        dte = _avg(bucket["dte_values"])
        ordered.append(
            {
                "key": key,
                "label": bucket["label"],
                "target_dte": bucket["target_dte"],
                "tickers": sorted(set(bucket["tickers"])),
                "fresh_tickers": sorted(set(bucket["fresh_tickers"])),
                "stale_tickers": sorted(set(bucket["stale_tickers"])),
                "eligible_for_scoring": bool(bucket["fresh_tickers"]),
                "dte": round(dte, 1) if dte is not None else None,
                "iv": iv,
                "expected_move_pct": expected_move,
                "pcr_volume": pcr,
                "skew": skew,
                "skew_reference": skew_reference,
                "skew_by_ticker": skew_by_ticker,
                "skew_dispersion": skew_dispersion,
                "nearby_net_gex": nearby_gex,
                "gamma_coverage": gamma,
                "source": ", ".join(sorted(bucket["sources"])),
                "resolved_expirations": sorted(set(bucket["resolved_expirations"])),
                "quality_warnings": _unique_warnings(bucket["warnings"])[:8],
                "summary": _horizon_summary(
                    str(bucket["label"]), iv, expected_move, pcr, skew, nearby_gex
                ),
            }
        )
    return ordered


def _aggregate_term_structure(results: list[dict]) -> dict[str, Any]:
    horizons = _aggregate_option_horizons(results)
    return _build_term_structure(horizons)


def _append_number(values: list[float], value: Any) -> None:
    number = _float_or_none(value)
    if number is not None:
        values.append(number)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _skew_entry(
    ticker: str, item: dict[str, Any], horizon: dict[str, Any]
) -> dict[str, Any] | None:
    detail = horizon.get("skew_detail")
    stale = bool(horizon.get("is_stale") or item.get("is_stale"))
    if isinstance(detail, dict):
        entry = {
            "ticker": ticker,
            "value": _float_or_none(detail.get("value")),
            "method": str(detail.get("method") or "unavailable"),
            "status": str(detail.get("status") or "unavailable"),
            "put_iv": _float_or_none(detail.get("put_iv")),
            "call_iv": _float_or_none(detail.get("call_iv")),
            "put_delta": _float_or_none(detail.get("put_delta")),
            "call_delta": _float_or_none(detail.get("call_delta")),
            "put_strike": _float_or_none(detail.get("put_strike")),
            "call_strike": _float_or_none(detail.get("call_strike")),
            "liquidity_status": str(detail.get("liquidity_status") or "unknown"),
            "warnings": list(detail.get("warnings") or []),
            "is_stale": stale,
            "data_as_of": str(
                horizon.get("data_as_of") or item.get("data_as_of") or ""
            ),
            "expiration": str(horizon.get("resolved_expiration") or ""),
        }
        return entry

    legacy_value = _float_or_none(horizon.get("skew"))
    if legacy_value is None:
        return None
    return {
        "ticker": ticker,
        "value": legacy_value,
        "method": "legacy_proxy",
        "status": "proxy",
        "put_iv": None,
        "call_iv": None,
        "put_delta": None,
        "call_delta": None,
        "put_strike": None,
        "call_strike": None,
        "liquidity_status": "unknown",
        "warnings": [
            "Legacy numeric skew has no 25-delta provenance and is display-only."
        ],
        "is_stale": stale,
        "data_as_of": str(horizon.get("data_as_of") or item.get("data_as_of") or ""),
        "expiration": str(horizon.get("resolved_expiration") or ""),
    }


def _is_fresh_direct_skew(entry: dict[str, Any] | None) -> bool:
    return bool(
        entry
        and entry.get("status") == "direct"
        and entry.get("method") == "delta_25_direct"
        and entry.get("liquidity_status") == "ok"
        and entry.get("value") is not None
        and not entry.get("is_stale")
    )


def _spy_skew_reference(
    skew_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    spy = skew_by_ticker.get("SPY")
    return dict(spy) if _is_fresh_direct_skew(spy) else None


def _direct_skew_dispersion(
    skew_by_ticker: dict[str, dict[str, Any]],
) -> float | None:
    values = [
        float(entry["value"])
        for entry in skew_by_ticker.values()
        if _is_fresh_direct_skew(entry)
    ]
    return round(max(values) - min(values), 6) if len(values) >= 2 else None


def _horizon_summary(
    label: str,
    iv: float | None,
    expected_move: float | None,
    pcr: float | None,
    skew: float | None,
    nearby_gex: float | None,
) -> str:
    parts = [label]
    if iv is not None:
        parts.append(f"IV={iv:.1%}")
    if expected_move is not None:
        parts.append(f"1σ={expected_move:.1%}")
    if pcr is not None:
        parts.append(f"PCR={pcr:.2f}")
    if skew is not None:
        parts.append(f"25Δ IVスキュー(SPY)={skew:.1%}")
    if nearby_gex is not None:
        parts.append("GEX=" + ("正" if nearby_gex > 0 else "負"))
    return " / ".join(parts)


def _aggregate_sources(results: list[dict]) -> str:
    sources = sorted({str(item.get("source") or "yfinance") for item in results})
    return ", ".join(sources) if sources else "yfinance"


def _latest_fetched_at(results: list[dict]) -> str:
    values = [
        str(item.get("fetched_at") or "") for item in results if item.get("fetched_at")
    ]
    return max(values) if values else ""


def _latest_value(results: list[dict], key: str) -> str:
    values = [str(item.get(key) or "") for item in results if item.get(key)]
    return max(values) if values else ""


def _first_value(results: list[dict], key: str) -> str:
    for item in results:
        value = str(item.get(key) or "")
        if value:
            return value
    return ""


def _aggregate_data_modes(results: list[dict]) -> str:
    modes = sorted(
        {str(item.get("data_mode") or "") for item in results if item.get("data_mode")}
    )
    return ", ".join(modes)


def _aggregate_value_set(results: list[dict], key: str) -> str:
    values = sorted({str(item.get(key) or "") for item in results if item.get(key)})
    return ", ".join(values)


def _sum_optional_values(results: list[dict], key: str) -> int | None:
    values = [int(item[key]) for item in results if item.get(key) is not None]
    return sum(values) if values else None


def _min_optional_values(results: list[dict], key: str) -> int | None:
    values = [int(item[key]) for item in results if item.get(key) is not None]
    return min(values) if values else None


def _aggregate_cache_status(results: list[dict]) -> str:
    statuses = {str(item.get("cache_status") or "live") for item in results}
    if not statuses:
        return "failed"
    if "stale_cache" in statuses:
        return "stale_cache"
    if "memory_cache" in statuses:
        return "memory_cache"
    if "persistent_cache" in statuses:
        return "persistent_cache"
    if "failed" in statuses:
        return "failed"
    return "live"


def _max_cache_age_seconds(results: list[dict]) -> float | None:
    ages = [
        float(item["cache_age_seconds"])
        for item in results
        if item.get("cache_age_seconds") is not None
    ]
    return max(ages) if ages else None


def _aggregate_gamma_coverage(results: list[dict]) -> float | None:
    total = sum(int(item.get("total_contracts") or 0) for item in results)
    if total <= 0:
        return None
    covered = sum(int(item.get("gamma_contracts") or 0) for item in results)
    return round(covered / total, 4)


def _aggregate_complete_status(results: list[dict], status: str) -> str:
    if status in {"failed", "not_applicable"}:
        return status
    statuses = [str(item.get("complete_status") or "") for item in results]
    if statuses and all(item == "complete" for item in statuses):
        return "complete"
    if any(item == "fallback" for item in statuses):
        return "fallback"
    if any(item in {"partial_greeks", "gex_unavailable"} for item in statuses):
        return "partial_greeks"
    if any(item == "provider_inactive" for item in statuses):
        return "provider_inactive"
    if any(item == "stale_cache" for item in statuses):
        return "stale_cache"
    if status == "partial":
        return "partial"
    return statuses[0] if statuses else status


def _option_underlying_price(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    """Use the chain's own underlying price when the provider supplies it."""

    for frame in (calls, puts):
        if "underlyingPrice" not in frame.columns:
            continue
        values = pd.to_numeric(frame["underlyingPrice"], errors="coerce").dropna()
        values = values[values > 0]
        if not values.empty:
            return float(values.iloc[0])
    return None
