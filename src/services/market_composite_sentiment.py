"""Explainable joint interpretation of volatility, options, and participation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from src.market_data import get_stock_data
from src.market_volatility_intelligence import CboeIndexResult, fetch_cboe_indices
from src.persistent_cache import repo_state_cache, utc_now_iso
from src.services.occ_put_call_service import (
    OccPutCallResult,
    load_occ_put_call_history,
    refresh_occ_put_call_latest,
)

COMPOSITE_VERSION = "market-composite-sentiment-v1"
RISK_RANK = {"none": -1, "low": 0, "medium": 1, "high": 2, "extreme": 3}


def build_market_composite_sentiment(
    option_items: list[dict[str, Any]] | None = None,
    *,
    history_provider: Callable[[str, str], pd.DataFrame] = get_stock_data,
    cboe_result: CboeIndexResult | None = None,
    refresh_occ: bool = True,
) -> dict[str, Any]:
    """Fetch the small live input set and build SPY/QQQ joint states."""

    if cboe_result is None:
        cboe_result = fetch_cboe_indices()
    frames = {
        ticker: history_provider(ticker, "1y")
        for ticker in ("SPY", "QQQ", "RSP", "IWM")
    }
    occ = {}
    for ticker in ("SPY", "QQQ"):
        occ[ticker] = (
            refresh_occ_put_call_latest(ticker)
            if refresh_occ
            else load_occ_put_call_history(ticker)
        )
    return compute_market_composite_sentiment(
        frames,
        cboe_result,
        option_items or [],
        occ,
        record_gamma=True,
    )


def compute_market_composite_sentiment(
    price_frames: dict[str, pd.DataFrame],
    cboe_result: CboeIndexResult,
    option_items: list[dict[str, Any]],
    occ_results: dict[str, OccPutCallResult],
    *,
    record_gamma: bool = False,
) -> dict[str, Any]:
    """Compute evidence-backed joint states without changing forecast probabilities."""

    targets = {}
    for ticker in ("SPY", "QQQ"):
        targets[ticker] = _target_composite(
            ticker,
            price_frames,
            cboe_result.data,
            _option_item(option_items, ticker),
            occ_results.get(ticker) or OccPutCallResult(symbol=ticker),
            record_gamma=record_gamma,
        )
    primary = targets.get("SPY") or _mixed_state("SPY", {})
    warnings = [
        *cboe_result.warnings,
        *[
            warning
            for result in occ_results.values()
            for warning in result.warnings[:3]
        ],
    ]
    return {
        "status": primary.get("status", "unavailable"),
        "state": primary.get("state", "mixed"),
        "state_label": primary.get("state_label", "材料混在"),
        "summary": primary.get("summary", "複合市場状態は判定できません。"),
        "risk_floor": primary.get("risk_floor", "none"),
        "reversal_watch": bool(primary.get("reversal_watch", False)),
        "targets": targets,
        "version": COMPOSITE_VERSION,
        "as_of": primary.get("as_of", ""),
        "source": "Cboe+OCC+ETF participation+option Greeks",
        "is_stale": cboe_result.is_stale,
        "is_partial": primary.get("status") != "confirmed" or cboe_result.is_partial,
        "integration_enabled": primary.get("status") == "confirmed"
        and not cboe_result.is_stale,
        "quality_warnings": warnings,
    }


def _target_composite(
    ticker: str,
    price_frames: dict[str, pd.DataFrame],
    cboe: pd.DataFrame,
    option_item: dict[str, Any],
    occ_result: OccPutCallResult,
    *,
    record_gamma: bool,
) -> dict[str, Any]:
    conditions, as_of = _conditions(
        ticker,
        price_frames,
        cboe,
        option_item,
        occ_result,
        record_gamma=record_gamma,
    )
    rules = [
        _rule(
            "downside_amplification",
            "下方向の増幅警戒",
            ("vix_rising_or_term_stress", "vvix_spike", "negative_gamma"),
            conditions,
            risk_floor="high",
            extreme_if=("term_stress", "breadth_weak"),
        ),
        _rule(
            "capitulation_rebound_watch",
            "悲観織り込み・反発候補",
            ("vix_high", "pcr_extreme", "positive_gamma_transition"),
            conditions,
            risk_floor="none",
            reversal_watch=True,
        ),
        _rule(
            "hidden_tail_hedging",
            "表面平静・テール警戒",
            ("vix_falling", "skew_high", "term_contango"),
            conditions,
            risk_floor="medium",
        ),
        _rule(
            "narrow_leadership",
            "少数銘柄主導",
            ("vix_not_high", "breadth_weak"),
            conditions,
            risk_floor="medium",
        ),
        _rule(
            "orderly_risk_on",
            "秩序あるリスクオン",
            (
                "vix_not_high",
                "skew_not_high",
                "term_contango",
                "positive_gamma",
                "breadth_strong",
            ),
            conditions,
            risk_floor="none",
        ),
    ]
    matched = [item for item in rules if item["status"] == "confirmed"]
    partial = [item for item in rules if item["status"] == "partial"]
    primary = (
        matched[0]
        if matched
        else partial[0]
        if partial
        else _mixed_state(ticker, conditions)
    )
    secondary = [item for item in [*matched, *partial] if item is not primary]
    risk_floor = (
        primary.get("risk_floor", "none")
        if primary.get("status") == "confirmed"
        else "none"
    )
    if (
        primary.get("state") == "downside_amplification"
        and conditions.get("term_stress", {}).get("matched") is True
        and conditions.get("breadth_weak", {}).get("matched") is True
    ):
        risk_floor = "extreme"
    return {
        **primary,
        "ticker": ticker,
        "as_of": as_of,
        "risk_floor": risk_floor,
        "conditions": conditions,
        "secondary_states": secondary,
        "evidence": [conditions[key] for key in primary.get("condition_keys", ())],
    }


def _conditions(
    ticker: str,
    price_frames: dict[str, pd.DataFrame],
    cboe: pd.DataFrame,
    option_item: dict[str, Any],
    occ_result: OccPutCallResult,
    *,
    record_gamma: bool,
) -> tuple[dict[str, dict[str, Any]], str]:
    cboe = _normalize_index(cboe)
    latest = cboe.ffill().iloc[-1] if not cboe.empty else pd.Series(dtype=float)
    vix = _series(cboe, "VIX")
    vvix = _series(cboe, "VVIX")
    skew = _series(cboe, "SKEW")
    vix_rank = _percentile(vix, _last(vix))
    vvix_rank = _percentile(vvix, _last(vvix))
    skew_rank = _percentile(skew, _last(skew))
    vix_change = _change(vix, 5)
    vvix_change = _change(vvix, 5)
    skew_change = _change(skew, 5)
    skew_as_of = (
        str(skew.dropna().index.max().date()) if not skew.dropna().empty else ""
    )
    vix9d_vix = _ratio(latest.get("VIX9D"), latest.get("VIX"))
    vix_vix3m = _ratio(latest.get("VIX"), latest.get("VIX3M"))
    term_stress = _any_true(
        _compare(vix9d_vix, 1.05, ">="),
        _compare(vix_vix3m, 1.00, ">="),
    )
    breadth = _breadth_metrics(price_frames)
    option = _option_metrics(option_item, ticker, record_gamma=record_gamma)
    pcr = _pcr_metrics(occ_result)

    conditions = {
        "vix_falling": _evidence(
            "VIX 5日変化",
            _compare(vix_change, -0.05, "<="),
            vix_change,
            "≤ -5%",
            "Cboe VIX",
        ),
        "vix_rising_or_term_stress": _evidence(
            "VIX上昇または期近ストレス",
            _any_true(_compare(vix_change, 0.10, ">="), term_stress),
            vix_change,
            "5日 +10% または期近逆転",
            "Cboe term structure",
        ),
        "vix_high": _evidence(
            "VIX履歴順位",
            _compare(vix_rank, 80, ">="),
            vix_rank,
            "≥ 80 percentile",
            "Cboe VIX",
        ),
        "vix_not_high": _evidence(
            "VIX履歴順位",
            _compare(vix_rank, 60, "<"),
            vix_rank,
            "< 60 percentile",
            "Cboe VIX",
        ),
        "skew_high": _evidence(
            "Cboe SKEW指数 テール警戒",
            _any_true(_compare(skew_rank, 80, ">="), _compare(skew_change, 0.03, ">=")),
            skew_rank,
            "順位80以上 または5日+3%",
            "Cboe SKEW",
            metric_kind="cboe_skew_index",
            raw_value=_last(skew),
            percentile=skew_rank,
            change_5d=skew_change,
            as_of=skew_as_of,
        ),
        "skew_not_high": _evidence(
            "Cboe SKEW指数 過熱なし",
            _compare(skew_rank, 80, "<"),
            skew_rank,
            "< 80 percentile",
            "Cboe SKEW",
            metric_kind="cboe_skew_index",
            raw_value=_last(skew),
            percentile=skew_rank,
            change_5d=skew_change,
            as_of=skew_as_of,
        ),
        "vvix_spike": _evidence(
            "VVIX急騰",
            _any_true(_compare(vvix_rank, 90, ">="), _compare(vvix_change, 0.10, ">=")),
            vvix_change,
            "順位90以上 または5日+10%",
            "Cboe VVIX",
        ),
        "term_stress": _evidence(
            "VIX期間構造ストレス",
            term_stress,
            vix_vix3m,
            "VIX9D/VIX≥1.05 または VIX/VIX3M≥1",
            "Cboe term structure",
        ),
        "term_contango": _evidence(
            "VIX期間構造順ザヤ",
            _compare(vix_vix3m, 1.00, "<"),
            vix_vix3m,
            "VIX/VIX3M < 1",
            "Cboe term structure",
        ),
        "pcr_extreme": _evidence(
            "Put/Call極端値",
            pcr["extreme"],
            pcr["percentile"],
            "≥ 90 percentile / 最低60観測",
            "OCC consolidated volume",
        ),
        "negative_gamma": _evidence(
            "ディーラーgamma",
            option["negative"],
            option["gex"],
            "GEX < 0 / coverage完全",
            option["source"],
        ),
        "positive_gamma": _evidence(
            "ディーラーgamma",
            option["positive"],
            option["gex"],
            "GEX > 0 / coverage完全",
            option["source"],
        ),
        "positive_gamma_transition": _evidence(
            "gamma正転換",
            option["positive_transition"],
            option["gex"],
            "直近3観測内に負→正",
            option["source"],
        ),
        "breadth_weak": _evidence(
            "市場参加度低下",
            breadth["weak"],
            breadth["rsp_spy_5d"],
            "RSP/SPY・IWM/SPYがともに5日-1%以下",
            "ETF participation proxy",
        ),
        "breadth_strong": _evidence(
            "市場参加度拡大",
            breadth["strong"],
            breadth["rsp_spy_5d"],
            "RSP/SPY 5日が0%以上",
            "ETF participation proxy",
        ),
    }
    as_of_values = [
        str(cboe.index.max().date()) if not cboe.empty else "",
        occ_result.as_of,
        option.get("as_of", ""),
    ]
    return conditions, max((item for item in as_of_values if item), default="")


def _rule(
    state: str,
    label: str,
    keys: tuple[str, ...],
    conditions: dict[str, dict[str, Any]],
    *,
    risk_floor: str,
    reversal_watch: bool = False,
    extreme_if: tuple[str, ...] = (),
) -> dict[str, Any]:
    values = [conditions[key].get("matched") for key in keys]
    if all(value is True for value in values):
        status = "confirmed"
    elif all(value is not False for value in values) and any(
        value is None for value in values
    ):
        status = "partial"
    else:
        status = "not_matched"
    summary = {
        "downside_amplification": "恐怖上昇とネガティブガンマが値動きを増幅しやすい状態です。",
        "capitulation_rebound_watch": "悲観の織り込みとgamma安定化による反発候補です。格上げには使いません。",
        "hidden_tail_hedging": "表面上は平静でも、テールヘッジ需要が強い状態です。",
        "narrow_leadership": "指数に比べ市場参加度が弱く、少数銘柄主導の状態です。",
        "orderly_risk_on": "低ストレス、正gamma、参加度拡大がそろった状態です。",
    }[state]
    return {
        "state": state,
        "state_label": label,
        "status": status,
        "summary": summary,
        "risk_floor": risk_floor,
        "reversal_watch": reversal_watch,
        "condition_keys": keys,
        "extreme_if": extreme_if,
    }


def _mixed_state(ticker: str, conditions: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "state": "mixed",
        "state_label": "材料混在",
        "status": "unavailable" if not conditions else "confirmed",
        "summary": "強弱材料が混在し、定義済みの複合状態には一致しません。",
        "risk_floor": "none",
        "reversal_watch": False,
        "condition_keys": (),
    }


def _option_metrics(
    item: dict[str, Any], ticker: str, *, record_gamma: bool
) -> dict[str, Any]:
    gex = item.get("gex") or {}
    value = _float(gex.get("nearby_net_gex")) if isinstance(gex, dict) else None
    coverage = _float(item.get("gamma_coverage"))
    complete = (
        bool(item.get("provider_active")) and item.get("complete_status") == "complete"
    )
    usable = value is not None and coverage is not None and coverage >= 0.8 and complete
    as_of = str(item.get("data_as_of") or item.get("resolved_expiration") or "")
    if usable and record_gamma:
        _record_gamma_snapshot(ticker, value, as_of)
    history = _gamma_history(ticker)
    transition = None
    if usable and value > 0 and len(history) >= 2:
        transition = bool((history["gex"].iloc[-4:-1] <= 0).any())
    elif usable and value <= 0:
        transition = False
    return {
        "gex": value if usable else None,
        "negative": value < 0 if usable else None,
        "positive": value > 0 if usable else None,
        "positive_transition": transition,
        "source": str(item.get("source") or "option Greeks"),
        "as_of": as_of,
    }


def _pcr_metrics(result: OccPutCallResult) -> dict[str, Any]:
    history = result.history
    if len(history) < 60 or "put_call_ratio" not in history:
        return {"percentile": None, "extreme": None}
    series = (
        pd.to_numeric(history["put_call_ratio"], errors="coerce").dropna().tail(252)
    )
    if len(series) < 60:
        return {"percentile": None, "extreme": None}
    percentile = _percentile(series, _last(series))
    return {"percentile": percentile, "extreme": _compare(percentile, 90, ">=")}


def _breadth_metrics(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    rsp_spy = _relative_change(frames, "RSP", "SPY", 5)
    iwm_spy = _relative_change(frames, "IWM", "SPY", 5)
    weak = (
        None
        if rsp_spy is None or iwm_spy is None
        else rsp_spy <= -0.01 and iwm_spy <= -0.01
    )
    strong = None if rsp_spy is None else rsp_spy >= 0
    return {
        "rsp_spy_5d": rsp_spy,
        "iwm_spy_5d": iwm_spy,
        "weak": weak,
        "strong": strong,
    }


def _record_gamma_snapshot(ticker: str, value: float, as_of: str) -> None:
    cache = repo_state_cache("market_gamma_snapshots")
    read = cache.read(ticker.lower(), fresh_seconds=0, stale_seconds=10 * 365 * 86400)
    records = list(read.payload.get("records") or [])
    date_key = _date_key(as_of) or datetime.utcnow().date().isoformat()
    records = [item for item in records if item.get("date") != date_key]
    records.append({"date": date_key, "gex": value})
    records = sorted(records, key=lambda item: str(item.get("date")))[-260:]
    cache.write(ticker.lower(), {"records": records}, fetched_at=utc_now_iso())


def _gamma_history(ticker: str) -> pd.DataFrame:
    read = repo_state_cache("market_gamma_snapshots").read(
        ticker.lower(), fresh_seconds=0, stale_seconds=10 * 365 * 86400
    )
    frame = pd.DataFrame(read.payload.get("records") or [])
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["gex"] = pd.to_numeric(frame["gex"], errors="coerce")
    return frame.dropna().set_index("date").sort_index()


def _evidence(
    label: str,
    matched: bool | None,
    value: Any,
    threshold: str,
    source: str,
    **metadata: Any,
) -> dict[str, Any]:
    return {
        "label": label,
        "status": "met"
        if matched is True
        else "not_met"
        if matched is False
        else "unavailable",
        "matched": matched,
        "value": _float(value),
        "threshold": threshold,
        "source": source,
        **metadata,
    }


def _option_item(items: list[dict[str, Any]], ticker: str) -> dict[str, Any]:
    return next(
        (item for item in items if str(item.get("ticker") or "").upper() == ticker), {}
    )


def _relative_change(
    frames: dict[str, pd.DataFrame], left: str, right: str, periods: int
) -> float | None:
    joined = pd.concat(
        [
            _close(frames.get(left)).rename("left"),
            _close(frames.get(right)).rename("right"),
        ],
        axis=1,
        sort=True,
    ).dropna()
    if len(joined) <= periods:
        return None
    ratio = joined["left"] / joined["right"]
    return float(ratio.pct_change(periods).iloc[-1])


def _close(frame: pd.DataFrame | None) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    column = next(
        (item for item in frame.columns if str(item).lower() == "close"), None
    )
    if column is None:
        return pd.Series(dtype=float)
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if isinstance(series.index, pd.DatetimeIndex) and series.index.tz is not None:
        series.index = series.index.tz_localize(None)
    return series.sort_index()


def _normalize_index(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if isinstance(result.index, pd.DatetimeIndex) and result.index.tz is not None:
        result.index = result.index.tz_localize(None)
    return result.sort_index()


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").dropna().tail(252)


def _last(series: pd.Series) -> float | None:
    return float(series.iloc[-1]) if not series.empty else None


def _change(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods or series.iloc[-periods - 1] == 0:
        return None
    return float(series.iloc[-1] / series.iloc[-periods - 1] - 1)


def _percentile(series: pd.Series, value: float | None) -> float | None:
    if value is None or len(series) < 60:
        return None
    return float((series <= value).mean() * 100)


def _ratio(left: Any, right: Any) -> float | None:
    a, b = _float(left), _float(right)
    return a / b if a is not None and b not in (None, 0) else None


def _compare(value: Any, threshold: float, operator: str) -> bool | None:
    number = _float(value)
    if number is None:
        return None
    if operator == ">=":
        return number >= threshold
    if operator == "<=":
        return number <= threshold
    if operator == "<":
        return number < threshold
    return number > threshold


def _any_true(*values: bool | None) -> bool | None:
    if any(value is True for value in values):
        return True
    if all(value is False for value in values):
        return False
    return None


def _date_key(value: str) -> str:
    if not value:
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else str(parsed.date())


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(number) else number
