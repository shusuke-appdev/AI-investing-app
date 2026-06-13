"""Sector and theme flow-pressure proxy monitor using free market data."""

from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

from src.yfinance_runtime import configure_yfinance_cache

FLOW_UNIVERSE = {
    "XLK": "情報技術",
    "XLC": "通信",
    "XLY": "一般消費財",
    "XLF": "金融",
    "XLV": "ヘルスケア",
    "XLI": "資本財",
    "XLP": "生活必需品",
    "XLE": "エネルギー",
    "XLU": "公益",
    "XLRE": "不動産",
    "XLB": "素材",
    "SMH": "半導体",
    "SOXX": "半導体指数",
    "QQQ": "Nasdaq 100",
    "IGV": "ソフトウェア",
    "ARKK": "高成長株",
    "BOTZ": "ロボティクス/AI",
    "HYG": "High Yield債",
    "LQD": "投資適格社債",
    "KBE": "銀行株",
    "KRE": "地銀株",
    "SPY": "S&P 500",
}


def build_sector_flow_monitor(market_type: str = "US") -> dict[str, Any]:
    """Rank leadership and flow-pressure proxies for US ETFs."""

    if market_type != "US":
        return {
            "status": "unavailable",
            "summary": "資金フローproxyは米国市場のみ対応です。",
            "leaders": [],
            "laggards": [],
            "warnings": [],
            "source": "not_applicable",
            "is_partial": True,
        }

    try:
        frame = _download_universe()
    except Exception as exc:
        return {
            "status": "failed",
            "summary": "資金フローproxyの取得に失敗しました。",
            "leaders": [],
            "laggards": [],
            "warnings": [str(exc)],
            "source": "yfinance",
            "is_partial": True,
        }

    rows = []
    warnings = []
    benchmark = _extract_close_volume(frame, "SPY")
    if benchmark.empty:
        return {
            "status": "failed",
            "summary": "SPYの基準データが不足しています。",
            "leaders": [],
            "laggards": [],
            "warnings": ["SPY benchmark data is unavailable."],
            "source": "yfinance",
            "is_partial": True,
        }

    for ticker, label in FLOW_UNIVERSE.items():
        if ticker == "SPY":
            continue
        data = _extract_close_volume(frame, ticker)
        if len(data) < 80:
            warnings.append(f"{ticker} has insufficient history.")
            continue
        row = _score_ticker(ticker, label, data, benchmark)
        if row:
            rows.append(row)

    rows.sort(key=lambda item: item["leadership_score"], reverse=True)
    leaders = rows[:8]
    laggards = sorted(rows, key=lambda item: item["leadership_score"])[:8]
    status = "risk_off" if _risk_off(rows) else "risk_on" if leaders else "unavailable"
    summary = _summary(status, leaders, laggards)
    return {
        "status": status,
        "summary": summary,
        "leaders": leaders,
        "laggards": laggards,
        "warnings": warnings[:8],
        "source": "yfinance_proxy",
        "is_partial": bool(warnings),
    }


def _download_universe() -> pd.DataFrame:
    configure_yfinance_cache()
    return yf.download(
        list(FLOW_UNIVERSE),
        period="1y",
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
        timeout=20,
    )


def _extract_close_volume(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    try:
        data = frame[ticker] if isinstance(frame.columns, pd.MultiIndex) else frame
    except KeyError:
        return pd.DataFrame()
    if "Close" not in data.columns or "Volume" not in data.columns:
        return pd.DataFrame()
    return data[["Close", "Volume"]].dropna().copy()


def _score_ticker(
    ticker: str,
    label: str,
    data: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> dict[str, Any] | None:
    aligned = pd.concat(
        [data["Close"], data["Volume"], benchmark["Close"]],
        axis=1,
        join="inner",
    ).dropna()
    aligned.columns = ["close", "volume", "benchmark"]
    if len(aligned) < 80:
        return None

    returns = aligned["close"].pct_change()
    dollar_volume = aligned["close"] * aligned["volume"]
    signed_dollar_volume = returns.apply(_sign) * dollar_volume
    flow_pressure = signed_dollar_volume.rolling(20).sum() / dollar_volume.rolling(
        60
    ).median().replace(0, pd.NA)
    relative_20d = _period_relative_return(aligned["close"], aligned["benchmark"], 20)
    relative_60d = _period_relative_return(aligned["close"], aligned["benchmark"], 60)
    flow_z = _zscore_latest(flow_pressure)
    rel20_z = _zscore_value(relative_20d, _rolling_relative(aligned, 20))
    rel60_z = _zscore_value(relative_60d, _rolling_relative(aligned, 60))
    ma50 = aligned["close"].rolling(50).mean().iloc[-1]
    trend = 1.0 if aligned["close"].iloc[-1] > ma50 else 0.0
    score = 0.4 * rel20_z + 0.25 * rel60_z + 0.25 * flow_z + 0.1 * trend
    return {
        "ticker": ticker,
        "label": label,
        "leadership_score": round(float(score), 2),
        "flow_pressure_z": round(float(flow_z), 2),
        "relative_return_20d": round(float(relative_20d * 100), 2),
        "relative_return_60d": round(float(relative_60d * 100), 2),
        "trend_above_ma50": bool(trend),
        "level": _score_level(score),
    }


def _period_relative_return(
    close: pd.Series, benchmark: pd.Series, window: int
) -> float:
    return float(
        (close.iloc[-1] / close.iloc[-window - 1] - 1)
        - (benchmark.iloc[-1] / benchmark.iloc[-window - 1] - 1)
    )


def _rolling_relative(aligned: pd.DataFrame, window: int) -> pd.Series:
    return aligned["close"].pct_change(window) - aligned["benchmark"].pct_change(window)


def _zscore_latest(series: pd.Series) -> float:
    clean = series.dropna()
    if len(clean) < 30:
        return 0.0
    mean = clean.rolling(120, min_periods=30).mean().iloc[-1]
    std = clean.rolling(120, min_periods=30).std().iloc[-1]
    if pd.isna(std) or std == 0:
        return 0.0
    return float((clean.iloc[-1] - mean) / std)


def _zscore_value(value: float, history: pd.Series) -> float:
    clean = history.dropna()
    if len(clean) < 30:
        return 0.0
    mean = clean.rolling(120, min_periods=30).mean().iloc[-1]
    std = clean.rolling(120, min_periods=30).std().iloc[-1]
    if pd.isna(std) or std == 0:
        return 0.0
    return float((value - mean) / std)


def _sign(value: float) -> int:
    if pd.isna(value):
        return 0
    return 1 if value > 0 else -1 if value < 0 else 0


def _score_level(score: float) -> str:
    if score >= 0.75:
        return "green"
    if score <= -0.75:
        return "red"
    return "gray"


def _risk_off(rows: list[dict[str, Any]]) -> bool:
    lookup = {row["ticker"]: row for row in rows}
    credit = lookup.get("HYG", {}).get("leadership_score", 0) < -0.75
    banks = (
        lookup.get("KBE", {}).get("leadership_score", 0) < -0.75
        and lookup.get("KRE", {}).get("leadership_score", 0) < -0.75
    )
    return bool(credit or banks)


def _summary(
    status: str,
    leaders: list[dict[str, Any]],
    laggards: list[dict[str, Any]],
) -> str:
    if status == "risk_off":
        return "信用ETFまたは銀行株に弱さがあり、リスクオフ寄りです。"
    if leaders:
        top = leaders[0]
        return f"{top['label']} ({top['ticker']}) に資金流入圧力proxyが集中しています。"
    if laggards:
        bottom = laggards[0]
        return f"{bottom['label']} ({bottom['ticker']}) が相対的に弱いです。"
    return "資金フローproxyを判定できません。"
