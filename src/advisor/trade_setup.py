"""Daily-data entry quality framework for individual stocks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from src.market_data import get_stock_data
from src.themes_config import get_themes

US_SECTOR_ETFS = {
    "technology": "XLK",
    "healthcare": "XLV",
    "financial services": "XLF",
    "financial": "XLF",
    "consumer cyclical": "XLY",
    "communication services": "XLC",
    "industrials": "XLI",
    "consumer defensive": "XLP",
    "energy": "XLE",
    "utilities": "XLU",
    "real estate": "XLRE",
    "basic materials": "XLB",
}


@dataclass
class SetupCheck:
    """One entry-framework check."""

    key: str
    label: str
    status: str = "unknown"
    points: float = 0.0
    max_points: float = 0.0
    value_display: str = "N/A"
    rationale: str = ""
    hard_rule: bool = False


@dataclass
class TradeSetupContext:
    """Serializable daily entry-framework result."""

    ticker: str
    market_type: str
    benchmark: str
    status: str = "insufficient_data"
    grade: str = "D"
    score: float = 0.0
    current_price: float = 0.0
    atr: float = 0.0
    atr_percent: float = 0.0
    adr_percent: float = 0.0
    rvol: float = 0.0
    vars_proxy: float = 0.0
    ma50: float = 0.0
    ma200: float = 0.0
    ma50_extension_atr: float = 0.0
    breakout_price: float = 0.0
    profit_extension_levels: dict[str, float] = field(default_factory=dict)
    checks: list[SetupCheck] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(item) for item in self.checks]
        payload["score_display"] = f"{self.score:.0f}/100"
        payload["atr_display"] = f"{self.atr:.2f} ({self.atr_percent:.2f}%)"
        payload["adr_display"] = f"{self.adr_percent:.2f}%"
        payload["rvol_display"] = f"{self.rvol:.2f}x"
        payload["vars_display"] = f"{self.vars_proxy:+.2f}"
        payload["ma50_extension_display"] = f"{self.ma50_extension_atr:.2f}x ATR"
        payload["blocked_display"] = _markdown_list(self.blocked_reasons)
        payload["warnings_display"] = _markdown_list(self.warnings)
        return payload


def evaluate_trade_setup(
    ticker: str,
    stock_info: dict[str, Any] | None = None,
    technical_data: dict[str, Any] | None = None,
    price_df: pd.DataFrame | None = None,
    benchmark_df: pd.DataFrame | None = None,
    history_provider: Callable[[str, str], pd.DataFrame] | None = None,
) -> TradeSetupContext:
    """Evaluate a stock using daily-data entry rules."""

    normalized = ticker.strip().upper()
    history_provider = history_provider or get_stock_data
    market_type = "JP" if normalized.endswith(".T") else "US"
    benchmark = "1306.T" if market_type == "JP" else "SPY"
    prices = _normalize(
        price_df if price_df is not None else history_provider(normalized, "1y")
    )
    benchmark_prices = _normalize(
        benchmark_df if benchmark_df is not None else history_provider(benchmark, "1y")
    )
    tech = technical_data or {}
    info = stock_info or {}
    result = TradeSetupContext(
        ticker=normalized,
        market_type=market_type,
        benchmark=benchmark,
    )

    if len(prices) < 200 or len(benchmark_prices) < 126:
        result.warnings.append(
            "Entry Framework requires at least 200 stock sessions and 126 benchmark sessions."
        )
        result.summary = "日足データ不足のためEntry Gateを判定できません。"
        return result

    close = prices["Close"].astype(float)
    high = prices["High"].astype(float)
    low = prices["Low"].astype(float)
    volume = prices["Volume"].astype(float)
    current = float(close.iloc[-1])
    atr_series = _atr_series(high, low, close)
    atr = float(atr_series.iloc[-1])
    atr_percent = atr / current * 100 if current > 0 else 0.0
    ma50 = float(close.rolling(50).mean().iloc[-1])
    ma200_series = close.rolling(200).mean()
    ma200 = float(ma200_series.iloc[-1])
    ma200_rising = ma200 > float(ma200_series.iloc[-20])
    ma50_extension_atr = (
        ((current - ma50) / current * 100) / atr_percent if atr_percent else 0.0
    )
    adr_percent = float(((high - low) / close.shift(1) * 100).tail(20).mean())
    prior_volume = float(volume.iloc[-51:-1].mean())
    rvol = float(volume.iloc[-1] / prior_volume) if prior_volume > 0 else 0.0
    market_relative = _relative_returns(close, benchmark_prices["Close"].astype(float))
    sector_label, sector_relative = _sector_relative_returns(
        normalized, market_type, info, close, history_provider
    )
    rs_line_high = _rs_line_new_high(close, benchmark_prices["Close"].astype(float))
    vars_proxy = market_relative.get("20d", 0.0) / max(atr_percent, 0.01)
    tight_range = (
        (float(high.tail(20).max()) - float(low.tail(20).min())) / current * 100
    )
    declining_volatility = float(atr_series.tail(10).mean()) < float(
        atr_series.iloc[-30:-10].mean()
    )
    vcp = bool((tech.get("vcp_data") or {}).get("is_vcp"))
    base = tech.get("base_recognition_data") or {}
    clean_base = bool(base.get("detected")) and tight_range <= 15.0
    pocket_pivot = _pocket_pivot(prices)
    breakout_price = _breakout_price(tech, high)
    breakout = breakout_price > 0 and current >= breakout_price and rvol >= 1.5

    checks = [
        _check(
            "market_rs",
            "市場相対強度",
            market_relative.get("20d", 0.0) > 0 and market_relative.get("63d", 0.0) > 0,
            12,
            f"20日 {market_relative.get('20d', 0.0):+.1f}% / 63日 {market_relative.get('63d', 0.0):+.1f}%",
            "市場ベンチマークを20日・63日の両方で上回る。",
        ),
        _check(
            "sector_rs",
            "セクター/テーマ相対強度",
            bool(sector_relative)
            and sector_relative.get("20d", 0.0) > 0
            and sector_relative.get("63d", 0.0) > 0,
            8,
            (
                f"{sector_label}: 20日 {sector_relative.get('20d', 0.0):+.1f}% / "
                f"63日 {sector_relative.get('63d', 0.0):+.1f}%"
                if sector_relative
                else "N/A"
            ),
            "米国はセクターETF、日本は所属テーマ銘柄群proxyと比較する。",
            unknown=not bool(sector_relative),
        ),
        _check(
            "rs_line_high",
            "RSライン高値",
            rs_line_high,
            5,
            "252日高値付近" if rs_line_high else "高値未更新",
            "銘柄価格÷市場ベンチマークのRSラインを確認する。",
        ),
        _check(
            "vars_proxy",
            "VARS proxy",
            vars_proxy >= 0.5,
            5,
            f"{vars_proxy:+.2f}",
            "20日市場超過リターンをATR%で調整した透明なproxy。",
        ),
        _check(
            "vcp",
            "VCP",
            vcp,
            12,
            "検出" if vcp else "未検出",
            "既存VCP検出結果を再利用する。",
        ),
        _check(
            "clean_base",
            "クリーンなベース",
            clean_base,
            8,
            f"20日レンジ {tight_range:.1f}%",
            "既存ベース認識と20日レンジ15%以内を確認する。",
        ),
        _check(
            "declining_volatility",
            "ボラティリティ収縮",
            declining_volatility,
            10,
            "収縮" if declining_volatility else "未収縮",
            "直近10日ATR平均が、その前20日ATR平均を下回る。",
        ),
        _check(
            "rvol",
            "RVOL",
            rvol >= 1.5,
            10,
            f"{rvol:.2f}x",
            "最新日出来高÷直前50日平均出来高。Entryトリガーは1.5x以上。",
        ),
        _check(
            "pocket_pivot",
            "Pocket Pivot proxy",
            pocket_pivot,
            5,
            "検出" if pocket_pivot else "未検出",
            "上昇日の出来高が直前10日間の下落日最大出来高を超え、終値が10MA上。",
        ),
        _check(
            "accumulation",
            "蓄積proxy",
            str(tech.get("obv_trend") or "") == "上昇",
            5,
            str(tech.get("obv_trend") or "N/A"),
            "既存OBVトレンドを機関投資家蓄積のproxyとして使う。",
            unknown="obv_trend" not in tech,
        ),
        _check(
            "adr",
            "ADR% / R余地",
            adr_percent >= 5.0,
            5,
            f"{adr_percent:.2f}%",
            "20日平均日中値幅率。5%以上を高R候補として扱う。",
        ),
        _check(
            "breakout",
            "日足Entryトリガー",
            breakout,
            10,
            f"Breakout {breakout_price:.2f} / RVOL {rvol:.2f}x",
            "日足ブレイクアウトとRVOLを組み合わせる。",
        ),
        _check(
            "ma50_extension",
            "50MAからのATR拡張",
            ma50_extension_atr <= 4.0,
            5,
            f"{ma50_extension_atr:.2f}x ATR",
            "4x ATR超はEntry不可。",
            hard_rule=True,
        ),
        _check(
            "ma200_trend",
            "200MAトレンド",
            ma200_rising,
            5,
            "上昇" if ma200_rising else "下降",
            "下降する200MAに逆らうEntryは禁止。",
            hard_rule=True,
        ),
    ]
    blocked = [
        item.rationale for item in checks if item.hard_rule and item.status == "fail"
    ]
    score = sum(item.points for item in checks)
    unknowns = [item.label for item in checks if item.status == "unknown"]
    grade = _grade(score)
    status = (
        "blocked"
        if blocked
        else "ready"
        if breakout and rvol >= 1.5 and score >= 75
        else "wait"
    )
    result.status = status
    result.grade = grade
    result.score = round(score, 1)
    result.current_price = current
    result.atr = atr
    result.atr_percent = atr_percent
    result.adr_percent = adr_percent
    result.rvol = rvol
    result.vars_proxy = vars_proxy
    result.ma50 = ma50
    result.ma200 = ma200
    result.ma50_extension_atr = ma50_extension_atr
    result.breakout_price = breakout_price
    result.profit_extension_levels = _profit_extension_levels(ma50, atr_percent)
    result.checks = checks
    result.blocked_reasons = blocked
    if unknowns:
        result.warnings.append("未判定: " + ", ".join(unknowns))
    result.warnings.append(
        "LoD、ORH、寄付き後30分、1-2時間確認、即時ギャップ抵抗は日足版では判定対象外。"
    )
    result.summary = _summary(status, grade, score, blocked)
    return result


def trade_setup_to_dict(context: TradeSetupContext) -> dict[str, Any]:
    return context.to_dict()


def _normalize(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    normalized = frame.copy()
    normalized.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
        inplace=True,
    )
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(normalized.columns):
        return pd.DataFrame()
    return normalized.dropna(subset=["High", "Low", "Close"])


def _atr_series(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous).abs(), (low - previous).abs()], axis=1
    ).max(axis=1)
    return true_range.rolling(14).mean().fillna(0.0)


def _relative_returns(stock: pd.Series, benchmark: pd.Series) -> dict[str, float]:
    aligned = pd.concat([stock.rename("stock"), benchmark.rename("benchmark")], axis=1)
    aligned = aligned.ffill().dropna()
    result = {}
    for key, window in {"20d": 20, "63d": 63, "126d": 126}.items():
        if len(aligned) <= window:
            continue
        stock_return = (
            aligned["stock"].iloc[-1] / aligned["stock"].iloc[-window - 1] - 1
        )
        benchmark_return = (
            aligned["benchmark"].iloc[-1] / aligned["benchmark"].iloc[-window - 1] - 1
        )
        result[key] = float((stock_return - benchmark_return) * 100)
    return result


def _rs_line_new_high(stock: pd.Series, benchmark: pd.Series) -> bool:
    aligned = pd.concat([stock.rename("stock"), benchmark.rename("benchmark")], axis=1)
    aligned = aligned.ffill().dropna()
    if len(aligned) < 126:
        return False
    rs_line = aligned["stock"] / aligned["benchmark"].replace(0, pd.NA)
    recent = rs_line.tail(252).dropna()
    return bool(not recent.empty and recent.iloc[-1] >= recent.max() * 0.99)


def _sector_relative_returns(
    ticker: str,
    market_type: str,
    info: dict[str, Any],
    stock_close: pd.Series,
    history_provider: Callable[[str, str], pd.DataFrame] | None = None,
) -> tuple[str, dict[str, float]]:
    history_provider = history_provider or get_stock_data
    if market_type == "US":
        sector = str(info.get("sector") or "").strip().lower()
        benchmark = US_SECTOR_ETFS.get(sector, "")
        prices = (
            _normalize(history_provider(benchmark, "1y"))
            if benchmark
            else pd.DataFrame()
        )
        relative = (
            _relative_returns(stock_close, prices["Close"].astype(float))
            if not prices.empty
            else {}
        )
        return benchmark or "N/A", relative

    for theme, tickers in get_themes("JP").items():
        normalized_tickers = [value.upper() for value in tickers]
        if ticker not in normalized_tickers:
            continue
        peer_profiles = []
        for peer in normalized_tickers:
            if peer == ticker:
                continue
            prices = _normalize(history_provider(peer, "1y"))
            if not prices.empty:
                peer_profiles.append(_return_profile(prices["Close"].astype(float)))
            if len(peer_profiles) >= 5:
                break
        stock_profile = _return_profile(stock_close)
        relative = {
            key: stock_profile[key] - float(pd.Series(values).median())
            for key in stock_profile
            if (values := [profile[key] for profile in peer_profiles if key in profile])
        }
        return f"{theme}中央値", relative

    fallback = _normalize(history_provider("1306.T", "1y"))
    relative = (
        _relative_returns(stock_close, fallback["Close"].astype(float))
        if not fallback.empty
        else {}
    )
    return "1306.T", relative


def _return_profile(close: pd.Series) -> dict[str, float]:
    result = {}
    for key, window in {"20d": 20, "63d": 63, "126d": 126}.items():
        if len(close) > window:
            result[key] = float((close.iloc[-1] / close.iloc[-window - 1] - 1) * 100)
    return result


def _pocket_pivot(prices: pd.DataFrame) -> bool:
    if len(prices) < 12:
        return False
    close = prices["Close"].astype(float)
    volume = prices["Volume"].astype(float)
    down_days = volume.iloc[-11:-1][close.iloc[-11:-1].diff() < 0]
    max_down_volume = float(down_days.max()) if not down_days.empty else 0.0
    ma10 = float(close.rolling(10).mean().iloc[-1])
    return bool(
        close.iloc[-1] > close.iloc[-2]
        and close.iloc[-1] > ma10
        and volume.iloc[-1] > max_down_volume
    )


def _breakout_price(technical: dict[str, Any], high: pd.Series) -> float:
    vcp = technical.get("vcp_data") or {}
    value = _number(vcp.get("breakout_price"))
    if value > 0:
        return value
    return float(high.iloc[-21:-1].max()) if len(high) >= 21 else 0.0


def _profit_extension_levels(ma50: float, atr_percent: float) -> dict[str, float]:
    return {
        f"{multiple}x": round(ma50 * (1 + multiple * atr_percent / 100), 2)
        for multiple in (4, 6, 8, 10)
    }


def _check(
    key: str,
    label: str,
    passed: bool,
    max_points: float,
    value_display: str,
    rationale: str,
    *,
    hard_rule: bool = False,
    unknown: bool = False,
) -> SetupCheck:
    status = "unknown" if unknown else "pass" if passed else "fail"
    return SetupCheck(
        key=key,
        label=label,
        status=status,
        points=max_points if passed and not unknown else 0.0,
        max_points=max_points,
        value_display=value_display,
        rationale=rationale,
        hard_rule=hard_rule,
    )


def _grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def _summary(status: str, grade: str, score: float, blocked: list[str]) -> str:
    if status == "blocked":
        return (
            f"Entry不可。Grade {grade} / {score:.0f}点。禁止条件: {'; '.join(blocked)}"
        )
    if status == "ready":
        return f"日足Entryトリガー成立。Grade {grade} / {score:.0f}点。"
    return f"監視継続。Grade {grade} / {score:.0f}点。Entryトリガー待ち。"


def _number(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- なし"
