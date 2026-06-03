"""IBD-style market regime classification using free local market data."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from src.advisor.market_monitor import track_distribution_days
from src.advisor.minervini_analyzer import detect_follow_through_day

REGIME_CONFIRMED_UPTREND = "confirmed_uptrend"
REGIME_UPTREND_UNDER_PRESSURE = "uptrend_under_pressure"
REGIME_RALLY_ATTEMPT = "rally_attempt"
REGIME_MARKET_IN_CORRECTION = "market_in_correction"


REGIME_LABELS = {
    REGIME_CONFIRMED_UPTREND: "Confirmed Uptrend",
    REGIME_UPTREND_UNDER_PRESSURE: "Uptrend Under Pressure",
    REGIME_RALLY_ATTEMPT: "Rally Attempt",
    REGIME_MARKET_IN_CORRECTION: "Market in Correction",
}


REGIME_SCORES = {
    REGIME_CONFIRMED_UPTREND: 0.9,
    REGIME_UPTREND_UNDER_PRESSURE: 0.1,
    REGIME_RALLY_ATTEMPT: -0.2,
    REGIME_MARKET_IN_CORRECTION: -0.9,
}


@dataclass
class BenchmarkRegimeInput:
    """Per-index inputs used to judge the market regime."""

    ticker: str
    close: float = 0.0
    change_1d: float = 0.0
    ma21: float | None = None
    ma50: float | None = None
    ma200: float | None = None
    above_ma21: bool = False
    above_ma50: bool = False
    above_ma200: bool = False
    distribution_count: int = 0
    distribution_level: str = "normal"
    ftd_status: str = ""
    is_ftd: bool = False
    days_since_bottom: int = 0
    data_quality: str = "unavailable"


@dataclass
class IbdMarketRegimeResult:
    """Current market-regime classification and score contribution."""

    status_key: str = REGIME_MARKET_IN_CORRECTION
    label: str = REGIME_LABELS[REGIME_MARKET_IN_CORRECTION]
    score: float = REGIME_SCORES[REGIME_MARKET_IN_CORRECTION]
    weight: float = 2.0
    exposure_level: str = "0-20%"
    rationale: str = ""
    action_summary: str = ""
    benchmarks: dict[str, dict[str, Any]] = field(default_factory=dict)
    quality_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_ibd_market_regime(
    spy_df: pd.DataFrame | None,
    ndx_df: pd.DataFrame | None = None,
) -> IbdMarketRegimeResult:
    """Classify an IBD-style regime from benchmark OHLCV data.

    This is an IBD-style approximation, not an official Market Pulse clone. It
    intentionally uses auditable rules from local OHLCV data: distribution days,
    follow-through days, rally attempts, and key moving-average pressure.
    """

    inputs = {
        "SPY": _benchmark_input("SPY", spy_df),
        "NDX": _benchmark_input("NDX", ndx_df),
    }
    available = [item for item in inputs.values() if item.data_quality == "ok"]
    if not available:
        return IbdMarketRegimeResult(
            rationale="指数のOHLCVデータ不足によりIBD式市場状態を判定できない。",
            quality_warnings=["IBD regime unavailable: benchmark data is missing."],
        )

    max_distribution = max(item.distribution_count for item in available)
    below_ma50_count = sum(not item.above_ma50 for item in available)
    below_ma200_count = sum(not item.above_ma200 for item in available)
    ftd_any = any(item.is_ftd for item in available)
    rally_any = any("ラリー試行" in item.ftd_status for item in available)
    correction_any = any("調整" in item.ftd_status for item in available)

    if (
        below_ma200_count >= 1
        or below_ma50_count == len(available)
        or max_distribution >= 8
        or correction_any
        and not ftd_any
    ):
        status_key = REGIME_MARKET_IN_CORRECTION
    elif rally_any and not ftd_any:
        status_key = REGIME_RALLY_ATTEMPT
    elif max_distribution >= 6 or below_ma50_count >= 1:
        status_key = REGIME_UPTREND_UNDER_PRESSURE
    else:
        status_key = REGIME_CONFIRMED_UPTREND

    rationale = _rationale(status_key, available, max_distribution, ftd_any, rally_any)
    return IbdMarketRegimeResult(
        status_key=status_key,
        label=REGIME_LABELS[status_key],
        score=REGIME_SCORES[status_key],
        weight=2.0,
        exposure_level=_exposure_level(status_key),
        rationale=rationale,
        action_summary=_action_summary(status_key),
        benchmarks={key: asdict(value) for key, value in inputs.items()},
        quality_warnings=[
            f"{key} benchmark data unavailable."
            for key, value in inputs.items()
            if value.data_quality != "ok"
        ],
    )


def _benchmark_input(ticker: str, data: pd.DataFrame | None) -> BenchmarkRegimeInput:
    frame = _normalize_ohlcv(data)
    if frame.empty or len(frame) < 50:
        return BenchmarkRegimeInput(
            ticker=ticker,
            ftd_status="データ不足",
            data_quality="insufficient_data",
        )

    close = frame["Close"].dropna()
    latest_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) >= 2 else latest_close
    ma21 = _last_ma(close, 21)
    ma50 = _last_ma(close, 50)
    ma200 = _last_ma(close, 200)
    distribution = track_distribution_days(frame)
    ftd = detect_follow_through_day(frame)

    return BenchmarkRegimeInput(
        ticker=ticker,
        close=round(latest_close, 2),
        change_1d=round((latest_close - prev_close) / prev_close * 100, 2)
        if prev_close
        else 0.0,
        ma21=ma21,
        ma50=ma50,
        ma200=ma200,
        above_ma21=ma21 is not None and latest_close >= ma21,
        above_ma50=ma50 is not None and latest_close >= ma50,
        above_ma200=ma200 is not None and latest_close >= ma200,
        distribution_count=int(distribution.get("count", 0)),
        distribution_level=str(distribution.get("level", "normal")),
        ftd_status=str(ftd.get("status", "")),
        is_ftd=bool(ftd.get("is_ftd", False)),
        days_since_bottom=int(ftd.get("days_since_bottom", 0)),
        data_quality="ok",
    )


def _normalize_ohlcv(data: pd.DataFrame | None) -> pd.DataFrame:
    if data is None or data.empty:
        return pd.DataFrame()
    frame = data.copy()
    frame.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
        inplace=True,
    )
    required = {"Close", "Volume"}
    if not required.issubset(frame.columns):
        return pd.DataFrame()
    if "High" not in frame.columns:
        frame["High"] = frame["Close"]
    if "Low" not in frame.columns:
        frame["Low"] = frame["Close"]
    return frame.tail(260)


def _last_ma(close: pd.Series, window: int) -> float | None:
    if len(close) < window:
        return None
    value = close.rolling(window).mean().iloc[-1]
    if pd.isna(value):
        return None
    return round(float(value), 2)


def _exposure_level(status_key: str) -> str:
    return {
        REGIME_CONFIRMED_UPTREND: "60-100%",
        REGIME_UPTREND_UNDER_PRESSURE: "30-60%",
        REGIME_RALLY_ATTEMPT: "10-30%",
        REGIME_MARKET_IN_CORRECTION: "0-20%",
    }[status_key]


def _action_summary(status_key: str) -> str:
    return {
        REGIME_CONFIRMED_UPTREND: "主導株と主導テーマの押し目を選別し、失敗銘柄は早く切る。",
        REGIME_UPTREND_UNDER_PRESSURE: "新規リスクを絞り、既存ポジションは利益保護と弱い銘柄の整理を優先する。",
        REGIME_RALLY_ATTEMPT: "買い急がず、FTDとリーダー候補の出来高を伴うブレイクを待つ。",
        REGIME_MARKET_IN_CORRECTION: "資金防衛を最優先し、次の主導セクター候補と反転条件の調査に集中する。",
    }[status_key]


def _rationale(
    status_key: str,
    inputs: list[BenchmarkRegimeInput],
    max_distribution: int,
    ftd_any: bool,
    rally_any: bool,
) -> str:
    below_ma50 = [item.ticker for item in inputs if not item.above_ma50]
    below_ma200 = [item.ticker for item in inputs if not item.above_ma200]
    phrases = [
        f"最大売り抜け日数={max_distribution}",
        f"FTD={'あり' if ftd_any else 'なし'}",
        f"ラリー試行={'あり' if rally_any else 'なし'}",
    ]
    if below_ma50:
        phrases.append("50日線割れ=" + ",".join(below_ma50))
    if below_ma200:
        phrases.append("200日線割れ=" + ",".join(below_ma200))
    return f"{REGIME_LABELS[status_key]}判定: " + "; ".join(phrases)
