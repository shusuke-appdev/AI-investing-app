"""Nikkei upside condition diagnostics for the market dashboard."""

from __future__ import annotations

import os
from typing import Any

from src.log_config import get_logger
from src.market_data import get_stock_data
from src.persistent_cache import utc_now_iso

logger = get_logger(__name__)

DIRECT = "direct"
PROXY = "proxy"
UNAVAILABLE = "unavailable"
MET = "met"
NOT_MET = "not_met"


CONDITION_DEFINITIONS = [
    {
        "condition_no": 1,
        "title": "日証金合計の売り残が8,000億円以上",
        "category": "Market Liquidity / Short Interest",
        "threshold": "8,000億円以上",
        "mechanism": "将来の強制買い戻し圧力となり、株価急騰の燃料になる。",
    },
    {
        "condition_no": 2,
        "title": "日経レバの信用倍率が1倍未満",
        "category": "Retail Sentiment / Supply and Demand",
        "threshold": "1倍未満",
        "mechanism": "弱気ポジションの偏りが踏み上げを誘発しやすい。",
    },
    {
        "condition_no": 3,
        "title": "日本株の優位性の拡大",
        "category": "Global Asset Allocation",
        "threshold": "日経/TOPIXがS&P500を相対アウトパフォーム",
        "mechanism": "グローバル資金配分で日本株流入が優先される。",
    },
    {
        "condition_no": 4,
        "title": "ショートカバーの発生",
        "category": "Price Action / Short Squeeze",
        "threshold": "日経の急反発 + 出来高増",
        "mechanism": "買い戻しが上昇を増幅する踏み上げスパイラルを作る。",
    },
    {
        "condition_no": 5,
        "title": "日経平均の理論値の大幅な上方修正",
        "category": "Fundamentals / Valuation",
        "threshold": "EPS/PER直接データなしの場合は価格トレンドで代替",
        "mechanism": "EPSや許容PERの上方修正が上値追いを正当化する。",
    },
    {
        "condition_no": 6,
        "title": "海外投資家の日本株爆買い ＆ 原油価格の下落",
        "category": "External Factors / Macro Catalyst",
        "threshold": "海外投資家買い越し + 原油安",
        "mechanism": "外部資金流入と原油安のコスト低下が同時に追い風になる。",
    },
]


def build_japan_conditions_context(
    market_data: dict[str, Any] | None = None,
    sector_flow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate the six Nikkei upside conditions with free data first."""

    market_data = market_data or {}
    snapshots = _market_snapshots()
    items = [
        _condition_1(),
        _condition_2(),
        _condition_3(snapshots),
        _condition_4(snapshots),
        _condition_5(snapshots),
        _condition_6(market_data, sector_flow),
    ]
    available = [item for item in items if item["status"] != UNAVAILABLE]
    score = sum(float(item["score"]) for item in items) / len(items)
    met_count = sum(1 for item in items if item["status"] == MET)
    proxy_count = sum(1 for item in items if item["source_type"] == PROXY)
    unavailable_count = sum(1 for item in items if item["status"] == UNAVAILABLE)

    return {
        "generated_at": utc_now_iso(),
        "score": round(score, 2),
        "score_label": _score_label(score),
        "met_count": met_count,
        "available_count": len(available),
        "proxy_count": proxy_count,
        "unavailable_count": unavailable_count,
        "items": items,
        "summary": _summary(score, met_count, proxy_count, unavailable_count),
        "quality_warnings": _quality_warnings(proxy_count, unavailable_count),
    }


def _condition_1() -> dict[str, Any]:
    value = _env_float("NIKKEI_JSF_SHORT_BALANCE_BILLION")
    if value is None:
        return _item(
            1,
            status=UNAVAILABLE,
            source_type=UNAVAILABLE,
            value="-",
            score=0.0,
            evidence="日証金の市場全体売り残は現行の無料自動取得経路では未取得。",
            assessment="直接データ待ち。手入力環境変数があれば判定可能。",
        )
    met = value >= 8000
    return _item(
        1,
        status=MET if met else NOT_MET,
        source_type=DIRECT,
        value=f"{value:,.0f}億円",
        score=1.0 if met else 0.0,
        evidence="NIKKEI_JSF_SHORT_BALANCE_BILLION from environment.",
        assessment="売り残が踏み上げ燃料として十分。" if met else "閾値未達。",
    )


def _condition_2() -> dict[str, Any]:
    value = _env_float("NIKKEI_LEVERAGE_MARGIN_RATIO")
    if value is None:
        return _item(
            2,
            status=UNAVAILABLE,
            source_type=UNAVAILABLE,
            value="-",
            score=0.0,
            evidence="1570.T の信用倍率は現行の無料自動取得経路では未取得。",
            assessment="直接データ待ち。手入力環境変数があれば判定可能。",
        )
    met = value < 1.0
    return _item(
        2,
        status=MET if met else NOT_MET,
        source_type=DIRECT,
        value=f"{value:.2f}倍",
        score=1.0 if met else 0.0,
        evidence="NIKKEI_LEVERAGE_MARGIN_RATIO from environment.",
        assessment="個人弱気の踏み上げ燃料あり。" if met else "信用倍率は閾値未達。",
    )


def _condition_3(snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nikkei = snapshots.get("^N225", {})
    spx = snapshots.get("^GSPC", {})
    if not nikkei.get("available") or not spx.get("available"):
        return _item(
            3,
            status=UNAVAILABLE,
            source_type=UNAVAILABLE,
            value="-",
            score=0.0,
            evidence="日経平均またはS&P500の履歴データ不足。",
            assessment="相対優位を判定できない。",
        )
    relative_5d = nikkei["change_5d"] - spx["change_5d"]
    relative_20d = nikkei["change_20d"] - spx["change_20d"]
    met = relative_5d > 0 and relative_20d > 0
    return _item(
        3,
        status=MET if met else NOT_MET,
        source_type=PROXY,
        value=f"5日 {relative_5d:+.2f}pt / 20日 {relative_20d:+.2f}pt",
        score=0.7 if met else 0.2 if relative_5d > 0 else 0.0,
        evidence="日経平均とS&P500の相対騰落率で代替判定。",
        assessment="日本株優位が拡大。" if met else "相対優位は未確認。",
    )


def _condition_4(snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nikkei = snapshots.get("^N225", {})
    if not nikkei.get("available"):
        return _item(
            4,
            status=UNAVAILABLE,
            source_type=UNAVAILABLE,
            value="-",
            score=0.0,
            evidence="日経平均の履歴データ不足。",
            assessment="ショートカバー代理判定ができない。",
        )
    change_1d = nikkei["change_1d"]
    change_5d = nikkei["change_5d"]
    volume_ratio = nikkei["volume_ratio"]
    met = change_1d >= 1.0 and change_5d > 0 and volume_ratio >= 1.05
    score = 0.75 if met else 0.35 if change_1d > 0 and change_5d > 0 else 0.0
    return _item(
        4,
        status=MET if met else NOT_MET,
        source_type=PROXY,
        value=f"1日 {change_1d:+.2f}% / 5日 {change_5d:+.2f}% / 出来高 {volume_ratio:.2f}x",
        score=score,
        evidence="急反発と出来高増をショートカバーの代理指標として使用。",
        assessment="買い戻し発生の疑いあり。" if met else "踏み上げ加速は未確認。",
    )


def _condition_5(snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nikkei = snapshots.get("^N225", {})
    if not nikkei.get("available"):
        return _item(
            5,
            status=UNAVAILABLE,
            source_type=UNAVAILABLE,
            value="-",
            score=0.0,
            evidence="日経平均の履歴データ不足。",
            assessment="理論値上方修正の代理判定ができない。",
        )
    change_20d = nikkei["change_20d"]
    change_60d = nikkei["change_60d"]
    met = change_20d >= 5.0 and change_60d > 0
    return _item(
        5,
        status=MET if met else NOT_MET,
        source_type=PROXY,
        value=f"20日 {change_20d:+.2f}% / 60日 {change_60d:+.2f}%",
        score=0.6 if met else 0.2 if change_20d > 0 else 0.0,
        evidence="EPS/PER直接改定データの代替として日経の中期上方トレンドを使用。",
        assessment="理論値上方修正を織り込む価格動作。"
        if met
        else "上方修正織り込みは弱い。",
    )


def _condition_6(
    market_data: dict[str, Any], sector_flow: dict[str, Any] | None
) -> dict[str, Any]:
    foreign_buying = _env_float("NIKKEI_FOREIGN_INVESTOR_NET_BUY_BILLION")
    oil_change = _market_change(market_data, "WTI Oil")
    jp_leader = (
        (sector_flow or {}).get("markets", {}).get("JP", {}).get("leaders", [])[:1]
    )
    jp_flow_score = float(jp_leader[0].get("flow_score", 0.0)) if jp_leader else 0.0

    if foreign_buying is not None:
        met = foreign_buying > 0 and oil_change < 0
        return _item(
            6,
            status=MET if met else NOT_MET,
            source_type=DIRECT if oil_change != 0 else PROXY,
            value=f"海外投資家 {foreign_buying:+.0f}億円 / WTI {oil_change:+.2f}%",
            score=1.0 if met else 0.2 if foreign_buying > 0 else 0.0,
            evidence="海外投資家買越額は環境変数、原油は市場データから判定。",
            assessment="外部資金流入と原油安が同時発生。"
            if met
            else "複合条件は未達。",
        )

    met = oil_change < 0 and jp_flow_score >= 25
    return _item(
        6,
        status=MET if met else NOT_MET,
        source_type=PROXY,
        value=f"WTI {oil_change:+.2f}% / JP flow {jp_flow_score:+.1f}",
        score=0.55 if met else 0.15 if oil_change < 0 else 0.0,
        evidence="海外投資家直接データがないため、原油安と日本株テーマ流入で代替判定。",
        assessment="外部追い風の一部を確認。" if met else "外部追い風は限定的。",
    )


def _market_snapshots() -> dict[str, dict[str, Any]]:
    return {
        ticker: _ticker_snapshot(ticker)
        for ticker in ("^N225", "^GSPC", "1321.T", "CL=F")
    }


def _ticker_snapshot(ticker: str) -> dict[str, Any]:
    try:
        df = get_stock_data(ticker, "3mo")
    except Exception as exc:
        logger.debug("Japan condition data fetch failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "available": False}
    if df.empty or "Close" not in df.columns:
        return {"ticker": ticker, "available": False}
    df = df.dropna(subset=["Close"])
    if len(df) < 2:
        return {"ticker": ticker, "available": False}
    closes = df["Close"].astype(float)
    volume_ratio = 1.0
    if "Volume" in df.columns:
        volumes = df["Volume"].astype(float)
        avg_volume = float(volumes.tail(20).mean())
        if avg_volume > 0:
            volume_ratio = float(volumes.iloc[-1]) / avg_volume
    current = float(closes.iloc[-1])
    return {
        "ticker": ticker,
        "available": True,
        "change_1d": _pct_change(current, _prior_value(closes, 1)),
        "change_5d": _pct_change(current, _prior_value(closes, 5)),
        "change_20d": _pct_change(current, _prior_value(closes, 20)),
        "change_60d": _pct_change(current, _prior_value(closes, 60)),
        "volume_ratio": max(0.0, min(5.0, volume_ratio)),
    }


def _item(
    condition_no: int,
    *,
    status: str,
    source_type: str,
    value: str,
    score: float,
    evidence: str,
    assessment: str,
) -> dict[str, Any]:
    definition = CONDITION_DEFINITIONS[condition_no - 1]
    return {
        **definition,
        "status": status,
        "status_label": _status_label(status, source_type),
        "source_type": source_type,
        "value": value,
        "score": round(score, 2),
        "evidence": evidence,
        "assessment": assessment,
    }


def _status_label(status: str, source_type: str) -> str:
    if status == UNAVAILABLE:
        return "データ不足"
    if status == MET and source_type == PROXY:
        return "代理達成"
    if status == MET:
        return "達成"
    if source_type == PROXY:
        return "代理未達"
    return "未達"


def _score_label(score: float) -> str:
    if score >= 0.65:
        return "強い"
    if score >= 0.4:
        return "中立"
    return "弱い"


def _summary(
    score: float, met_count: int, proxy_count: int, unavailable_count: int
) -> str:
    return (
        f"総合 {score:.0%} / 達成 {met_count}件 / "
        f"代理 {proxy_count}件 / データ不足 {unavailable_count}件"
    )


def _quality_warnings(proxy_count: int, unavailable_count: int) -> list[str]:
    warnings = []
    if proxy_count:
        warnings.append(f"Nikkei conditions include {proxy_count} proxy evaluations.")
    if unavailable_count:
        warnings.append(
            f"Nikkei conditions have {unavailable_count} unavailable direct data points."
        )
    return warnings


def _market_change(market_data: dict[str, Any], name: str) -> float:
    item = market_data.get(name) or {}
    try:
        return float(item.get("change", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _env_float(name: str) -> float | None:
    value = os.environ.get(name)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _prior_value(series, periods: int) -> float:
    if len(series) > periods:
        return float(series.iloc[-periods - 1])
    return float(series.iloc[0])


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current - previous) / previous * 100.0
