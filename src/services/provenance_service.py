"""Build auditable provenance shared by UI and AI contexts."""

from __future__ import annotations

from typing import Any

from src.services.analysis_context import ProvenanceItem, ProvenanceKind


def market_summary_provenance(
    *, fetched_at: str, has_market_data: bool
) -> list[ProvenanceItem]:
    return [
        _item(
            "market.indices",
            "主要市場データ",
            ProvenanceKind.DIRECT if has_market_data else ProvenanceKind.UNAVAILABLE,
            source="market_data providers",
            as_of=fetched_at,
            method="Provider quotes and market history.",
            limitation="" if has_market_data else "市場データを取得できませんでした。",
            risk_level="low" if has_market_data else "high",
        )
    ]


def market_medium_provenance(
    *,
    fetched_at: str,
    monitor: dict[str, Any],
    ibd_regime: dict[str, Any],
    microstructure: dict[str, Any],
    sector_flow: dict[str, Any],
    flow_monitor: dict[str, Any],
    japan_conditions: dict[str, Any],
) -> list[ProvenanceItem]:
    yield_spread = monitor.get("yield_spread") or {}
    yield_available = bool(yield_spread.get("available", False))
    return [
        _item(
            "market.ibd_regime",
            "IBD式市場状態",
            ProvenanceKind.PROXY if ibd_regime else ProvenanceKind.UNAVAILABLE,
            source="SPY / Nasdaq 100 OHLCV",
            as_of=fetched_at,
            method="Distribution day, rally attempt, FTD and moving-average rules.",
            limitation="公式IBD Market Pulseではない無料データ近似。",
            risk_level="medium",
        ),
        _item(
            "market.microstructure",
            "市場マイクロストラクチャー",
            ProvenanceKind.PROXY if microstructure else ProvenanceKind.UNAVAILABLE,
            source="SPY price/volume and option summary",
            as_of=fetched_at,
            method="CTA positioning, Amihud liquidity and unwind score heuristics.",
            limitation="実際のCTAポジションや板情報ではない。",
            risk_level="high",
        ),
        _item(
            "market.sector_flow",
            "セクター・テーマ資金流入",
            ProvenanceKind.PROXY if sector_flow else ProvenanceKind.UNAVAILABLE,
            source="Representative ETFs and configured theme baskets",
            as_of=fetched_at,
            method="Relative return, volume ratio and participation scoring.",
            limitation="発行体公表の資金流入額ではない。",
            risk_level="high",
        ),
        _item(
            "market.etf_leadership",
            "ETFリーダーシップ",
            ProvenanceKind.PROXY if flow_monitor else ProvenanceKind.UNAVAILABLE,
            source=str(flow_monitor.get("source") or "yfinance"),
            as_of=fetched_at,
            method="Signed dollar-volume and relative-strength proxy.",
            limitation="ETFの公式ファンドフローではない。",
            risk_level="high",
        ),
        _item(
            "market.nikkei_conditions",
            "日経平均上昇6条件",
            ProvenanceKind.PROXY if japan_conditions else ProvenanceKind.UNAVAILABLE,
            source="Direct optional inputs and market proxies",
            as_of=fetched_at,
            method="Mixed direct, proxy and unavailable condition scoring.",
            limitation=(
                f"代理評価 {japan_conditions.get('proxy_count', 0)}件、"
                f"直接データ不足 {japan_conditions.get('unavailable_count', 0)}件。"
            ),
            risk_level="high",
        ),
        _item(
            "market.yield_spread",
            "株式イールドスプレッド",
            ProvenanceKind.COMPUTED if yield_available else ProvenanceKind.UNAVAILABLE,
            source="US 10Y yield and index valuation metrics",
            as_of=fetched_at,
            method="Index earnings yield minus US 10Y yield.",
            limitation=(
                ""
                if yield_available
                else "必要な利回りまたはPERが不足。固定値では補完しない。"
            ),
            risk_level="medium" if yield_available else "high",
        ),
    ]


def market_high_provenance(
    *,
    fetched_at: str,
    credit_stress: dict[str, Any],
    distortions: dict[str, Any],
) -> list[ProvenanceItem]:
    credit_kind = (
        ProvenanceKind.STALE_CACHE
        if credit_stress.get("is_stale")
        else ProvenanceKind.COMPUTED
        if credit_stress
        else ProvenanceKind.UNAVAILABLE
    )
    return [
        _item(
            "market.credit_stress",
            "信用ストレス速度",
            credit_kind,
            source=str(credit_stress.get("source") or "FRED and market confirmations"),
            as_of=str(credit_stress.get("fetched_at") or fetched_at),
            method="Three-month deltas and rolling z-scores.",
            limitation="FRED系列の公表遅延とstale cache利用の可能性がある。",
            risk_level="medium",
        ),
        _item(
            "market.distortions",
            "市場の歪み検知",
            ProvenanceKind.MODEL_OUTPUT if distortions else ProvenanceKind.UNAVAILABLE,
            source="Theme fundamental and flow scoring",
            as_of=fetched_at,
            method="Difference between heuristic fundamental and flow scores.",
            limitation="スコア定義に依存する調査候補であり売買シグナルではない。",
            risk_level="high",
        ),
    ]


def option_provenance(
    *, fetched_at: str, source: str, status: str, items: list[dict[str, Any]]
) -> list[ProvenanceItem]:
    qualities = {str(item.get("data_quality") or "") for item in items}
    has_marketdata = "marketdata.app" in source
    kind = (
        ProvenanceKind.ESTIMATED
        if "estimated" in qualities
        else ProvenanceKind.COMPUTED
        if items
        else ProvenanceKind.UNAVAILABLE
    )
    return [
        _item(
            "market.options",
            "オプション分析",
            kind,
            source=source,
            as_of=fetched_at,
            method=(
                "IV and Greeks are direct MarketData.app fields; PCR, Max Pain and GEX "
                "are computed from the bounded option chain."
                if has_marketdata
                else "PCR, IV, Max Pain and GEX computed from available option chains."
            ),
            limitation=(
                "欠損Gammaを推定したGEXを含む場合がある。"
                if kind == ProvenanceKind.ESTIMATED
                else "GEXのCall正・Put負は簡易なディーラー建玉方向仮定。"
                if has_marketdata
                else "Greeks欠損時はGEXを非表示にする。"
            ),
            risk_level="high" if kind == ProvenanceKind.ESTIMATED else "medium",
        )
    ]


def stock_provenance(
    *,
    ticker: str,
    has_profile: bool,
    has_history: bool,
    has_technical: bool,
    probabilistic: dict[str, Any],
    trend_follow: dict[str, Any],
    trade_setup: dict[str, Any],
    sector_theme: dict[str, Any],
    news_status: str,
) -> list[ProvenanceItem]:
    return [
        _item(
            f"stock.{ticker}.profile",
            "企業概要・バリュエーション",
            ProvenanceKind.DIRECT if has_profile else ProvenanceKind.UNAVAILABLE,
            source="market_data providers",
            method="Provider company profile and valuation fields.",
            limitation="" if has_profile else "企業概要を取得できませんでした。",
            risk_level="low" if has_profile else "high",
        ),
        _item(
            f"stock.{ticker}.history",
            "株価履歴",
            ProvenanceKind.DIRECT if has_history else ProvenanceKind.UNAVAILABLE,
            source="market_data providers",
            method="Daily OHLCV history.",
            limitation="" if has_history else "株価履歴を取得できませんでした。",
            risk_level="low" if has_history else "high",
        ),
        _item(
            f"stock.{ticker}.technical",
            "テクニカル総合評価",
            ProvenanceKind.COMPUTED if has_technical else ProvenanceKind.UNAVAILABLE,
            source="local technical analysis",
            method="Rule-based indicators and weighted score.",
            limitation="指標と閾値に依存するローカル算出値。",
            risk_level="medium",
        ),
        _item(
            f"stock.{ticker}.smart",
            "SMART基準評価",
            ProvenanceKind.PROXY,
            source="Latest available company metrics and market state",
            method="Best-effort simplified SMART criteria.",
            limitation="複数年・複数四半期の正式SMART判定ではなく、ROAによるROE代替を含みうる。",
            risk_level="high",
        ),
        _item(
            f"stock.{ticker}.probabilistic",
            "確率シグナル",
            ProvenanceKind.MODEL_OUTPUT
            if probabilistic
            else ProvenanceKind.UNAVAILABLE,
            source="Local historical-distribution model",
            method="Similar-state forward returns, walk-forward checks and sizing rules.",
            limitation="将来リターンの保証ではない。固定取引コストとサンプル定義に依存。",
            risk_level="high",
        ),
        _item(
            f"stock.{ticker}.trend_follow",
            "Trend-Follow Diagnostics",
            ProvenanceKind.COMPUTED if trend_follow else ProvenanceKind.UNAVAILABLE,
            source="Local daily backtest diagnostics",
            method="Next-open execution; Close is used only when Open is unavailable.",
            limitation="Close約定proxyを使う場合がある。",
            risk_level="medium",
        ),
        _item(
            f"stock.{ticker}.trade_setup",
            "Entry Framework",
            ProvenanceKind.PROXY if trade_setup else ProvenanceKind.UNAVAILABLE,
            source="Daily OHLCV and local technical analysis",
            method="Relative strength, contraction, volume and ATR positioning rules.",
            limitation="LoD、ORH、寄付き後ルールなど分足依存条件は判定しない。",
            risk_level="high",
        ),
        _item(
            f"stock.{ticker}.sector_theme",
            "セクター・テーマ評価",
            ProvenanceKind.PROXY if sector_theme else ProvenanceKind.UNAVAILABLE,
            source="Configured theme baskets and local scoring",
            method="Heuristic fundamental and relative-flow scoring.",
            limitation="公式セクター資金流入や企業ガイダンスの直接評価ではない。",
            risk_level="high",
        ),
        _item(
            f"stock.{ticker}.news",
            "最新ニュース",
            ProvenanceKind.DIRECT
            if news_status == "available"
            else ProvenanceKind.UNAVAILABLE,
            source=news_status,
            method="Provider or news aggregation result.",
            limitation=""
            if news_status == "available"
            else "ニュース取得が部分的または利用不可。",
            risk_level="medium",
        ),
    ]


def stale_cache_provenance(*, fetched_at: str, source: str) -> ProvenanceItem:
    return _item(
        "market.context_cache",
        "市場コンテキストキャッシュ",
        ProvenanceKind.STALE_CACHE,
        source=source,
        as_of=fetched_at,
        method="Last successful persisted market context.",
        limitation="現在値ではなく、外部取得失敗時の過去成功データ。",
        risk_level="high",
    )


def _item(
    item_id: str,
    label: str,
    kind: ProvenanceKind,
    *,
    source: str = "",
    as_of: str = "",
    method: str = "",
    limitation: str = "",
    risk_level: str = "low",
) -> ProvenanceItem:
    return ProvenanceItem(
        item_id=item_id,
        label=label,
        kind=kind,
        source=source,
        as_of=as_of,
        method=method,
        limitation=limitation,
        risk_level=risk_level,
    )
