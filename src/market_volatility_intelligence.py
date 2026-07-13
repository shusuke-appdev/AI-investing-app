"""Free-data market volatility, sentiment, and top-risk diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from typing import Any

import numpy as np
import pandas as pd
import requests

from src.economic_data_provider import fetch_fred_series
from src.persistent_cache import repo_state_cache, utc_now_iso

CBOE_BASE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices"
CBOE_SYMBOLS = (
    "VIX",
    "VIX1D",
    "VIX9D",
    "VIX3M",
    "VVIX",
    "SKEW",
    "VXN",
    "RVX",
    "DSPX",
    "VIXEQ",
)
CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


@dataclass
class CboeIndexResult:
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    source: str = ""
    fetched_at: str = ""
    is_stale: bool = False
    is_partial: bool = False
    warnings: list[str] = field(default_factory=list)
    symbol_status: dict[str, dict[str, Any]] = field(default_factory=dict)


def fetch_cboe_indices(symbols: tuple[str, ...] = CBOE_SYMBOLS) -> CboeIndexResult:
    """Fetch official Cboe index history with persistent stale fallback."""

    cache = repo_state_cache("cboe_index_cache")
    rows: list[pd.DataFrame] = []
    warnings: list[str] = []
    symbol_status: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        key = symbol.lower()
        cached = cache.read(key, fresh_seconds=6 * 3600, stale_seconds=7 * 86400)
        if cached.status == "fresh":
            frame = _frame_from_records(cached.payload.get("records") or [], symbol)
            if not frame.empty:
                rows.append(frame)
                symbol_status[symbol] = _cboe_symbol_status(
                    frame,
                    status="available",
                    cache_status="persistent_cache",
                )
                continue
        try:
            response = requests.get(
                f"{CBOE_BASE_URL}/{symbol}_History.csv",
                headers={"User-Agent": "AI-investing-app/1.0"},
                timeout=8,
            )
            response.raise_for_status()
            frame = _parse_cboe_csv(response.text, symbol)
            if frame.empty:
                raise ValueError("empty Cboe history")
            rows.append(frame)
            cache.write(key, {"records": _records(frame, symbol), "source": "cboe"})
            symbol_status[symbol] = _cboe_symbol_status(
                frame,
                status="available",
                cache_status="live",
            )
        except Exception as exc:
            warnings.append(f"{symbol}: {exc}")
            if cached.is_available:
                frame = _frame_from_records(cached.payload.get("records") or [], symbol)
                if not frame.empty:
                    rows.append(frame)
                    symbol_status[symbol] = _cboe_symbol_status(
                        frame,
                        status="stale",
                        cache_status="stale_cache",
                        warning=str(exc),
                        is_stale=True,
                    )
                    continue
            symbol_status[symbol] = {
                "status": "unavailable",
                "source": "cboe_official",
                "as_of": "",
                "is_stale": False,
                "row_count": 0,
                "cache_status": "failed",
                "warning": str(exc),
            }
    combined = (
        pd.concat(rows, axis=1, sort=True).sort_index() if rows else pd.DataFrame()
    )
    return CboeIndexResult(
        data=combined,
        source="cboe_official" if not combined.empty else "unavailable",
        fetched_at=utc_now_iso(),
        is_stale=any(item.get("is_stale", False) for item in symbol_status.values()),
        is_partial=any(
            item.get("status") != "available" for item in symbol_status.values()
        ),
        warnings=warnings,
        symbol_status=symbol_status,
    )


def fetch_cnn_fear_greed() -> dict[str, Any]:
    """Fetch CNN as a non-critical external reference with stale fallback."""

    cache = repo_state_cache("cnn_fear_greed_cache")
    cached = cache.read("latest", fresh_seconds=6 * 3600, stale_seconds=7 * 86400)
    if cached.status == "fresh":
        return {**cached.payload, "cache_status": "persistent_cache"}
    try:
        response = requests.get(
            CNN_FEAR_GREED_URL,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.cnn.com/markets/fear-and-greed",
            },
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()
        current = payload.get("fear_and_greed") or payload.get("fearAndGreed") or {}
        score = _float(current.get("score"))
        if score is None:
            raise ValueError("CNN response did not contain a current score")
        result = {
            "status": "available",
            "score": round(score, 1),
            "rating": str(current.get("rating") or ""),
            "as_of": str(current.get("timestamp") or payload.get("timestamp") or ""),
            "source": "CNN Fear & Greed",
            "cache_status": "live",
            "is_stale": False,
        }
        cache.write("latest", result)
        return result
    except Exception as exc:
        if cached.is_available:
            return {
                **cached.payload,
                "status": "stale",
                "cache_status": "stale_cache",
                "is_stale": True,
                "error": str(exc),
            }
        return {
            "status": "unavailable",
            "score": None,
            "rating": "",
            "source": "CNN Fear & Greed",
            "cache_status": "failed",
            "is_stale": False,
            "error": str(exc),
        }


def build_market_volatility_regime(
    spy_df: pd.DataFrame | None,
    *,
    cboe_result: CboeIndexResult | None = None,
    credit_stress: dict[str, Any] | None = None,
    ibd_regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an explainable market volatility regime and staged posture."""

    result = cboe_result or fetch_cboe_indices()
    data = result.data
    if data.empty or "VIX" not in data:
        return {
            "regime": "unavailable",
            "label": "ボラティリティ判定不可",
            "posture": "Watch",
            "confidence": "low",
            "summary": "Cboeボラティリティ履歴を取得できませんでした。",
            "metrics": {},
            "forward_outcomes": {},
            "evidence": result.warnings,
            "invalidation": [],
            "source": result.source,
        }
    latest = data.ffill().iloc[-1]
    vix = float(latest["VIX"])
    vix9d_ratio = _ratio(latest.get("VIX9D"), vix)
    vix3m_ratio = _ratio(vix, latest.get("VIX3M"))
    vix_rank = _percentile(data["VIX"].dropna(), vix)
    vvix = _float(latest.get("VVIX"))
    skew = _float(latest.get("SKEW"))
    rapid_credit = bool((credit_stress or {}).get("rapid_stress", False))

    if vix3m_ratio is not None and vix3m_ratio > 1.05 and vix_rank >= 80:
        regime = (
            "persistent_stress" if vix9d_ratio and vix9d_ratio > 1.0 else "shock_rising"
        )
    elif vix_rank >= 90:
        regime = "panic_mean_reversion_candidate"
    elif vix_rank <= 20 and (vvix is None or vvix < 95):
        regime = "complacent"
    elif vix3m_ratio is not None and vix3m_ratio < 0.95 and vix_rank >= 50:
        regime = "normalization"
    else:
        regime = "healthy_risk_on"
    labels = {
        "persistent_stress": "ストレス継続",
        "shock_rising": "ショック上昇",
        "panic_mean_reversion_candidate": "パニック・反発候補",
        "complacent": "低ボラ・楽観",
        "normalization": "正常化",
        "healthy_risk_on": "健全なリスクオン",
    }
    outcomes = _historical_outcomes(data, spy_df)
    probability_up = outcomes.get("20d", {}).get("probability_up")
    expected = outcomes.get("20d", {}).get("mean_return")
    confidence = "medium" if outcomes.get("sample_size", 0) >= 30 else "low"
    stabilization = regime in {"normalization", "healthy_risk_on"}
    posture = "Watch"
    if regime in {"persistent_stress", "shock_rising"} or rapid_credit:
        posture = "Defensive"
    elif (
        stabilization
        and confidence != "low"
        and probability_up is not None
        and probability_up >= 0.55
        and expected is not None
        and expected > 0
    ):
        posture = (
            "Staged"
            if (ibd_regime or {}).get("status_key") == "confirmed_uptrend"
            else "Pilot"
        )
    return {
        "regime": regime,
        "label": labels[regime],
        "posture": posture,
        "confidence": confidence,
        "summary": f"{labels[regime]} / 段階姿勢 {posture}",
        "metrics": {
            "vix": round(vix, 2),
            "vix_percentile": round(vix_rank, 1),
            "vix9d_vix": _round(vix9d_ratio, 3),
            "vix_vix3m": _round(vix3m_ratio, 3),
            "vvix": _round(vvix, 2),
            "skew": _round(skew, 2),
        },
        "forward_outcomes": outcomes,
        "evidence": [
            f"VIX {vix:.2f}（履歴順位 {vix_rank:.0f}）",
            f"VIX9D/VIX {_text(vix9d_ratio)} / VIX/VIX3M {_text(vix3m_ratio)}",
        ],
        "invalidation": [
            "VIX期近の再バックワーデーション",
            "直近安値割れ",
            "信用ストレス加速",
        ],
        "source": result.source,
        "is_stale": result.is_stale,
        "warnings": result.warnings,
    }


def build_local_sentiment_composite(
    spy_df: pd.DataFrame | None,
    tlt_df: pd.DataFrame | None,
    *,
    cboe_result: CboeIndexResult | None = None,
    credit_stress: dict[str, Any] | None = None,
    cnn_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an independently reproducible 0-100 sentiment composite."""

    components: list[dict[str, Any]] = []
    spy = _close(spy_df)
    if len(spy) >= 125:
        score = _clamp(
            50 + ((spy.iloc[-1] / spy.rolling(125).mean().iloc[-1]) - 1) * 500
        )
        components.append(_component("momentum", "SPY対125日線", score, "computed"))
    result = cboe_result or fetch_cboe_indices(("VIX",))
    if "VIX" in result.data and len(result.data["VIX"].dropna()) >= 50:
        vix = result.data["VIX"].dropna()
        ratio = vix.iloc[-1] / vix.rolling(50).mean().iloc[-1]
        components.append(
            _component(
                "volatility", "VIX対50日平均", _clamp(50 - (ratio - 1) * 150), "direct"
            )
        )
    tlt = _close(tlt_df)
    if len(spy) >= 21 and len(tlt) >= 21:
        joined = pd.concat([spy.rename("spy"), tlt.rename("tlt")], axis=1).dropna()
        if len(joined) >= 21:
            relative = (
                joined["spy"].pct_change(20).iloc[-1]
                - joined["tlt"].pct_change(20).iloc[-1]
            )
            components.append(
                _component(
                    "safe_haven", "SPY対TLT 20日", _clamp(50 + relative * 300), "proxy"
                )
            )
    stress_score = _float((credit_stress or {}).get("score"))
    if stress_score is None:
        rapid = (credit_stress or {}).get("rapid_stress")
        if rapid is not None:
            stress_score = 0.8 if rapid else 0.3
    if stress_score is not None:
        components.append(
            _component(
                "credit",
                "クレジットストレス逆数",
                _clamp((1 - stress_score) * 100),
                "proxy",
            )
        )
    score = (
        round(float(np.mean([item["score"] for item in components])), 1)
        if components
        else None
    )
    return {
        "score": score,
        "label": _sentiment_label(score),
        "summary": f"独自心理指数 {score:.0f} / {_sentiment_label(score)}"
        if score is not None
        else "独自心理指数はデータ不足",
        "coverage": f"{len(components)}/7",
        "components": components,
        "source": "local_equal_weight_composite",
        "cnn_reference": cnn_reference or {},
        "quality_warnings": ["欠損構成要素は残存要素で再正規化しています。"]
        if len(components) < 7
        else [],
    }


def build_top_risk_signposts(
    *,
    sentiment: dict[str, Any] | None = None,
    credit_stress: dict[str, Any] | None = None,
    low_pe_relative_6m: float | None = None,
) -> dict[str, Any]:
    """Build the explicitly implementable BofA-inspired subset."""

    fred = fetch_fred_series(
        ["UMCSENT", "T10Y2Y", "T10Y3M", "DRTSCILM"],
        start="2015-01-01",
        prefer_stale_cache=True,
        csv_timeout=8,
        use_pandas_datareader_fallback=False,
    )
    frame = fred.data
    rows = []
    rows.append(
        _z_signpost(
            "consumer_optimism_proxy", "消費者楽観proxy", frame.get("UMCSENT"), 1.0
        )
    )
    sentiment_score = _float((sentiment or {}).get("score"))
    rows.append(
        _simple_signpost(
            "equity_optimism_proxy", "株高期待proxy", sentiment_score, 75.0, exact=False
        )
    )
    rows.append(
        _unknown_signpost(
            "valuation_inflation_zscore", "PE＋インフレ 10年Zスコア", exact=False
        )
    )
    rows.append(
        _simple_signpost(
            "low_pe_underperformance",
            "低PE劣後proxy（RPG-RPV、6か月）",
            low_pe_relative_6m,
            0.025,
            exact=False,
        )
    )
    curve = pd.concat(
        [
            frame.get("T10Y2Y", pd.Series(dtype=float)),
            frame.get("T10Y3M", pd.Series(dtype=float)),
        ],
        axis=1,
    )
    curve_value = float(curve.min(axis=1).tail(126).min()) if not curve.empty else None
    rows.append(
        _simple_signpost(
            "yield_curve_inversion",
            "逆イールド（直近6か月）",
            curve_value,
            0.0,
            less_than=True,
            exact=True,
        )
    )
    credit_score = _float((credit_stress or {}).get("score"))
    rows.append(
        _simple_signpost(
            "credit_complacency_proxy",
            "クレジット過度楽観proxy",
            credit_score,
            0.25,
            less_than=True,
            exact=False,
        )
    )
    sloos = frame.get("DRTSCILM", pd.Series(dtype=float)).dropna()
    rows.append(
        _simple_signpost(
            "sloos_tightening",
            "SLOOS引締め",
            float(sloos.iloc[-1]) if not sloos.empty else None,
            0.0,
            exact=True,
        )
    )
    triggered = sum(item["status"] == "triggered" for item in rows)
    known = sum(item["status"] != "unknown" for item in rows)
    return {
        "label": "BofA-inspired 実装可能サブセット",
        "summary": f"{triggered}/{known} 発火（判定可能項目のみ）",
        "triggered": triggered,
        "known": known,
        "coverage": f"{known}/7",
        "items": rows,
        "omitted": [
            "Sell Side Indicator",
            "S&P 500 LT growth expectations",
            "M&A deal count Z-score",
        ],
        "source": fred.source,
        "quality_warnings": fred.warnings,
    }


def _parse_cboe_csv(text: str, symbol: str) -> pd.DataFrame:
    frame = pd.read_csv(StringIO(text))
    date_column = next(
        (c for c in frame.columns if str(c).strip().upper() == "DATE"), None
    )
    if date_column is None:
        return pd.DataFrame()
    close_column = next((c for c in frame.columns if "CLOSE" in str(c).upper()), None)
    if close_column is None:
        close_column = next(
            (c for c in frame.columns if str(c).strip().upper() == symbol.upper()),
            None,
        )
    if close_column is None:
        close_column = next(
            (
                c
                for c in frame.columns
                if c != date_column
                and pd.to_numeric(frame[c], errors="coerce").notna().any()
            ),
            None,
        )
    if close_column is None:
        return pd.DataFrame()
    dates = pd.to_datetime(frame[date_column], errors="coerce")
    values = pd.to_numeric(frame[close_column], errors="coerce")
    return pd.DataFrame({symbol: values.values}, index=dates).dropna().sort_index()


def _cboe_symbol_status(
    frame: pd.DataFrame,
    *,
    status: str,
    cache_status: str,
    warning: str = "",
    is_stale: bool = False,
) -> dict[str, Any]:
    index = frame.index.dropna()
    as_of = str(index.max().date()) if len(index) else ""
    return {
        "status": status,
        "source": "cboe_official",
        "as_of": as_of,
        "is_stale": is_stale,
        "row_count": len(frame),
        "cache_status": cache_status,
        "warning": warning,
    }


def _historical_outcomes(
    cboe: pd.DataFrame, spy_df: pd.DataFrame | None
) -> dict[str, Any]:
    spy = _close(spy_df)
    if spy.empty or "VIX" not in cboe:
        return {"sample_size": 0}
    frame = pd.concat([cboe.ffill(), spy.rename("spy")], axis=1, sort=True).dropna(
        subset=["VIX", "spy"]
    )
    if len(frame) < 100:
        return {"sample_size": 0}
    state = pd.DataFrame(index=frame.index)
    for column in ("VIX", "VVIX", "SKEW"):
        if column in frame:
            mean = frame[column].rolling(252, min_periods=60).mean()
            std = frame[column].rolling(252, min_periods=60).std().replace(0, np.nan)
            state[column] = (frame[column] - mean) / std
    distances = ((state - state.iloc[-1]) ** 2).mean(axis=1).pow(0.5).dropna()
    selected = []
    for date in distances.sort_values().index:
        if date == frame.index[-1] or any(
            abs((date - item).days) < 14 for item in selected
        ):
            continue
        selected.append(date)
        if len(selected) == 50:
            break
    outcomes: dict[str, Any] = {"sample_size": len(selected)}
    for horizon in (5, 20, 60):
        forward = frame["spy"].shift(-horizon) / frame["spy"] - 1
        values = forward.reindex(selected).dropna()
        outcomes[f"{horizon}d"] = {
            "mean_return": _round(values.mean(), 4) if not values.empty else None,
            "probability_up": _round((values > 0).mean(), 3)
            if not values.empty
            else None,
            "worst_return": _round(values.min(), 4) if not values.empty else None,
        }
    return outcomes


def _z_signpost(
    item_id: str, label: str, series: pd.Series | None, threshold: float
) -> dict[str, Any]:
    values = series.dropna() if series is not None else pd.Series(dtype=float)
    if len(values) < 20:
        return _unknown_signpost(item_id, label, exact=False)
    rolling = values.tail(120)
    std = rolling.std()
    z = (values.iloc[-1] - rolling.mean()) / std if std else np.nan
    return _simple_signpost(item_id, label, _float(z), threshold, exact=False)


def _simple_signpost(
    item_id: str,
    label: str,
    value: float | None,
    threshold: float,
    *,
    less_than: bool = False,
    exact: bool,
) -> dict[str, Any]:
    if value is None:
        return _unknown_signpost(item_id, label, exact=exact)
    hit = value < threshold if less_than else value > threshold
    return {
        "id": item_id,
        "label": label,
        "status": "triggered" if hit else "not_triggered",
        "value": round(value, 3),
        "threshold": threshold,
        "kind": "exact" if exact else "proxy",
    }


def _unknown_signpost(item_id: str, label: str, *, exact: bool) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "status": "unknown",
        "value": None,
        "threshold": None,
        "kind": "exact" if exact else "proxy",
    }


def _records(frame: pd.DataFrame, symbol: str) -> list[dict[str, Any]]:
    return [
        {"date": str(date.date()), symbol: float(value)}
        for date, value in frame[symbol].dropna().items()
    ]


def _frame_from_records(records: list[dict[str, Any]], symbol: str) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if frame.empty or "date" not in frame or symbol not in frame:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"])
    frame[symbol] = pd.to_numeric(frame[symbol], errors="coerce")
    return frame.set_index("date")[[symbol]].dropna()


def _close(frame: pd.DataFrame | None) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    column = next((c for c in frame.columns if str(c).lower() == "close"), None)
    series = (
        pd.to_numeric(frame[column], errors="coerce").dropna()
        if column is not None
        else pd.Series(dtype=float)
    )
    if isinstance(series.index, pd.DatetimeIndex) and series.index.tz is not None:
        series.index = series.index.tz_localize(None)
    return series


def _ratio(left: Any, right: Any) -> float | None:
    a, b = _float(left), _float(right)
    return a / b if a is not None and b not in (None, 0) else None


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(number) else number


def _round(value: Any, digits: int) -> float | None:
    number = _float(value)
    return round(number, digits) if number is not None else None


def _percentile(series: pd.Series, value: float) -> float:
    return float((series <= value).mean() * 100)


def _clamp(value: float) -> float:
    return float(max(0, min(100, value)))


def _component(item_id: str, label: str, score: float, kind: str) -> dict[str, Any]:
    return {"id": item_id, "label": label, "score": round(score, 1), "kind": kind}


def _sentiment_label(score: float | None) -> str:
    if score is None:
        return "データ不足"
    if score < 25:
        return "Extreme Fear"
    if score < 45:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 75:
        return "Greed"
    return "Extreme Greed"


def _text(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"
