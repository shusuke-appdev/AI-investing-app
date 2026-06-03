"""Credit stress velocity monitor for US market crisis diagnostics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from src.economic_data_provider import fetch_fred_series
from src.market_data import get_stock_data
from src.persistent_cache import utc_now_iso

TIER1_SERIES = {
    "BAA10Y": "BAA信用スプレッド",
    "KCFSI": "KC金融ストレス",
}
CONFIRMATION_SERIES = {
    "BAMLH0A0HYM2": "HY OAS",
    "BAMLC0A4CBBB": "BBB OAS",
    "STLFSI4": "St. Louis金融ストレス",
    "NFCI": "Chicago金融環境",
    "ICSA": "失業保険申請",
    "AMTMNO": "製造業新規受注proxy",
}
RAPID_STRESS_Z_THRESHOLD = 0.5


def build_credit_stress_monitor(market_type: str = "US") -> dict[str, Any]:
    """Build a US credit stress monitor from FRED and liquid ETF proxies."""

    if market_type != "US":
        return {
            "status": "unavailable",
            "status_label": "米国市場のみ対応",
            "level": "gray",
            "summary": "信用ストレス速度監視は米国市場のみ対応です。",
            "rapid_stress": False,
            "indicators": [],
            "confirmations": [],
            "warnings": [],
            "source": "not_applicable",
            "fetched_at": utc_now_iso(),
            "is_partial": True,
        }

    start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=365 * 10)
    result = fetch_fred_series(list(TIER1_SERIES), start=start)
    confirmation_result = fetch_fred_series(list(CONFIRMATION_SERIES), start=start)
    frame = result.data
    confirmation_frame = confirmation_result.data
    warnings = [*result.warnings, *confirmation_result.warnings]

    indicators = [
        _series_velocity_payload(frame.get(series_id), series_id, label)
        for series_id, label in TIER1_SERIES.items()
    ]
    confirmations = [
        _series_velocity_payload(confirmation_frame.get(series_id), series_id, label)
        for series_id, label in CONFIRMATION_SERIES.items()
        if series_id in confirmation_frame.columns
    ]
    confirmations.extend(_market_confirmation_payloads())

    baa = _indicator_by_series(indicators, "BAA10Y")
    kc = _indicator_by_series(indicators, "KCFSI")
    baa_hot = _is_hot(baa)
    kc_hot = _is_hot(kc)
    baa_available = bool(baa and baa.get("latest_date"))
    kc_available = bool(kc and kc.get("latest_date"))
    if baa_available and kc_available and baa_hot and kc_hot:
        status = "rapid_stress"
        label = "rapid_stress"
        level = "red"
        summary = "信用スプレッドと金融ストレスが同時に加速しています。"
    elif baa_available and kc_available and (baa_hot or kc_hot):
        status = "watch"
        label = "警戒"
        level = "orange"
        summary = "信用または金融ストレスの片側に加速兆候があります。"
    elif baa_available and kc_available:
        status = "equity_adjustment"
        label = "通常調整寄り"
        level = "green"
        summary = "信用市場への同時伝染はまだ確認されていません。"
    else:
        status = "unavailable"
        label = "判定不能"
        level = "gray"
        summary = "Tier1指標が不足しているため判定できません。"
        warnings.append("BAA10Y or KCFSI data is unavailable.")

    return {
        "status": status,
        "status_label": label,
        "level": level,
        "summary": summary,
        "rapid_stress": status == "rapid_stress",
        "indicators": indicators,
        "confirmations": confirmations,
        "warnings": warnings,
        "source": result.source,
        "fetched_at": result.fetched_at,
        "is_stale": result.is_stale,
        "is_partial": result.is_partial
        or confirmation_result.is_partial
        or status == "unavailable",
        "cache_status": result.cache_status,
        "cache_age_seconds": result.cache_age_seconds,
    }


def _series_velocity_payload(
    series: pd.Series | None,
    series_id: str,
    label: str,
) -> dict[str, Any]:
    if series is None:
        return _empty_indicator(series_id, label, "series missing")
    clean = series.dropna().sort_index()
    if len(clean) < 4:
        return _empty_indicator(series_id, label, "not enough observations")

    deltas = _three_month_delta_series(clean)
    latest_delta = deltas.dropna().iloc[-1] if not deltas.dropna().empty else None
    z_score = _latest_z_score(deltas)
    latest = clean.iloc[-1]
    latest_date = clean.index[-1]
    stale_days = (pd.Timestamp.now(tz="UTC").tz_localize(None) - latest_date).days
    return {
        "series_id": series_id,
        "label": label,
        "latest": round(float(latest), 4),
        "latest_date": latest_date.date().isoformat(),
        "delta_3m": round(float(latest_delta), 4) if latest_delta is not None else 0.0,
        "z_score": round(float(z_score), 2) if z_score is not None else 0.0,
        "is_hot": bool(z_score is not None and z_score > RAPID_STRESS_Z_THRESHOLD),
        "level": _z_level(z_score),
        "stale_days": int(stale_days),
        "warning": "データが古い可能性があります" if stale_days > 45 else "",
    }


def _three_month_delta_series(series: pd.Series) -> pd.Series:
    values = []
    index = series.index
    for date, value in series.items():
        target = date - pd.DateOffset(months=3)
        position = index.searchsorted(target, side="right") - 1
        if position < 0:
            values.append(None)
            continue
        values.append(float(value) - float(series.iloc[position]))
    return pd.Series(values, index=index, dtype="float64")


def _latest_z_score(deltas: pd.Series) -> float | None:
    clean = deltas.dropna()
    if len(clean) < 24:
        return None
    spacing = clean.index.to_series().diff().dt.days.median()
    window = 60 if spacing and spacing > 20 else 1260
    min_periods = 24 if window == 60 else 120
    rolling_mean = clean.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = clean.rolling(window=window, min_periods=min_periods).std()
    latest_std = rolling_std.iloc[-1]
    if pd.isna(latest_std) or latest_std == 0:
        return None
    return float((clean.iloc[-1] - rolling_mean.iloc[-1]) / latest_std)


def _market_confirmation_payloads() -> list[dict[str, Any]]:
    pairs = [
        ("HYG", "LQD", "HYG/LQD 20日相対"),
        ("KBE", "SPY", "銀行株/SPY 20日相対"),
        ("KRE", "SPY", "地銀株/SPY 20日相対"),
    ]
    payloads = []
    for numerator, denominator, label in pairs:
        try:
            num = get_stock_data(numerator, "3mo")["Close"].dropna()
            den = get_stock_data(denominator, "3mo")["Close"].dropna()
            aligned = pd.concat([num, den], axis=1, join="inner").dropna()
            aligned.columns = ["num", "den"]
            if len(aligned) < 21:
                continue
            relative = (aligned["num"].iloc[-1] / aligned["num"].iloc[-21] - 1) - (
                aligned["den"].iloc[-1] / aligned["den"].iloc[-21] - 1
            )
            payloads.append(
                {
                    "series_id": f"{numerator}/{denominator}",
                    "label": label,
                    "latest": round(float(relative * 100), 2),
                    "latest_date": aligned.index[-1].date().isoformat(),
                    "delta_3m": round(float(relative * 100), 2),
                    "z_score": 0.0,
                    "is_hot": relative < -0.03,
                    "level": "orange" if relative < -0.03 else "green",
                    "stale_days": 0,
                    "warning": "",
                }
            )
        except Exception:
            continue
    return payloads


def _indicator_by_series(
    indicators: list[dict[str, Any]], series_id: str
) -> dict[str, Any] | None:
    return next(
        (item for item in indicators if item.get("series_id") == series_id), None
    )


def _is_hot(indicator: dict[str, Any] | None) -> bool:
    return bool(indicator and indicator.get("is_hot"))


def _z_level(value: float | None) -> str:
    if value is None:
        return "gray"
    if value > 1.0:
        return "red"
    if value > RAPID_STRESS_Z_THRESHOLD:
        return "orange"
    return "green"


def _empty_indicator(series_id: str, label: str, warning: str) -> dict[str, Any]:
    return {
        "series_id": series_id,
        "label": label,
        "latest": 0.0,
        "latest_date": "",
        "delta_3m": 0.0,
        "z_score": 0.0,
        "is_hot": False,
        "level": "gray",
        "stale_days": 0,
        "warning": warning,
    }
