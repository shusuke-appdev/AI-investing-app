"""
オプション分析モジュール
GEX (Gamma Exposure)、PCR (Put/Call Ratio)、Gamma Wallの計算を行います。
Finnhub APIから取得したGreeksを活用し、より正確な分析を提供します。
"""

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from .data_provider import DataProvider
from .market_data import get_option_chain

# ============================================================
# 内部ヘルパー: データ取得（1回だけ実行）
# ============================================================


def _fetch_option_data(
    ticker: str,
) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, float]]:
    """
    オプションチェーンと現在価格を1回で取得する内部ヘルパー。

    Returns:
        (calls_df, puts_df, current_price) のタプル、またはNone
    """
    option_data = get_option_chain(ticker)
    if option_data is None:
        return None

    calls, puts = option_data

    # 現在価格取得（DataProvider経由: Finnhub→yfinanceフォールバック内蔵）
    current_price = DataProvider.get_current_price(ticker)

    if not current_price:
        return None

    return calls, puts, current_price


# ============================================================
# 個別計算関数（データを引数で受け取る版 + 後方互換のticker版）
# ============================================================


def calculate_pcr(
    ticker: str = "",
    *,
    calls: Optional[pd.DataFrame] = None,
    puts: Optional[pd.DataFrame] = None,
) -> Optional[dict]:
    """
    Put/Call Ratioを計算します。

    Args:
        ticker: 銘柄コード（calls/putsが未指定の場合に使用）
        calls: コールオプションDataFrame（事前取得済みデータ）
        puts: プットオプションDataFrame（事前取得済みデータ）

    Returns:
        PCR情報の辞書
    """
    if calls is None or puts is None:
        option_data = get_option_chain(ticker)
        if option_data is None:
            return None
        calls, puts = option_data

    # Volume PCR
    call_volume = calls["volume"].sum() if "volume" in calls.columns else 0
    put_volume = puts["volume"].sum() if "volume" in puts.columns else 0
    volume_pcr = put_volume / call_volume if call_volume > 0 else 0

    # Open Interest PCR
    call_oi = calls["openInterest"].sum() if "openInterest" in calls.columns else 0
    put_oi = puts["openInterest"].sum() if "openInterest" in puts.columns else 0
    oi_pcr = put_oi / call_oi if call_oi > 0 else 0

    return {
        "ticker": ticker,
        "volume_pcr": volume_pcr,
        "oi_pcr": oi_pcr,
        "total_call_volume": call_volume,
        "total_put_volume": put_volume,
        "total_call_oi": call_oi,
        "total_put_oi": put_oi,
    }


def calculate_gex(
    ticker: str = "",
    *,
    calls: Optional[pd.DataFrame] = None,
    puts: Optional[pd.DataFrame] = None,
    current_price: float = 0.0,
) -> Optional[dict]:
    """
    Gamma Exposure (GEX) を計算します。
    Finnhub APIから取得したGreeksを使用し、APIデータがない場合のみ推定値を使用。

    Args:
        ticker: 銘柄コード（データ未指定時に使用）
        calls: コールオプションDataFrame
        puts: プットオプションDataFrame
        current_price: 現在の株価

    Returns:
        GEX情報の辞書（ストライク別GEXとWall情報を含む）
    """
    if calls is None or puts is None or current_price == 0.0:
        fetched = _fetch_option_data(ticker)
        if fetched is None:
            return None
        calls, puts, current_price = fetched

    gex_data = []

    # Callsの処理
    for _, row in calls.iterrows():
        strike = row.get("strike", 0)
        oi = row.get("openInterest", 0)
        gamma = row.get("gamma", 0)

        if pd.isna(gamma) or gamma == 0:
            moneyness = (
                abs(strike - current_price) / current_price if current_price > 0 else 1
            )
            gamma = max(0.001, 0.05 * np.exp(-5 * moneyness))

        gex = gamma * oi * 100 * current_price
        gex_data.append({"strike": strike, "gex": gex, "type": "call", "oi": oi})

    # Putsの処理
    for _, row in puts.iterrows():
        strike = row.get("strike", 0)
        oi = row.get("openInterest", 0)
        gamma = row.get("gamma", 0)

        if pd.isna(gamma) or gamma == 0:
            moneyness = (
                abs(strike - current_price) / current_price if current_price > 0 else 1
            )
            gamma = max(0.001, 0.05 * np.exp(-5 * moneyness))

        gex = -gamma * oi * 100 * current_price
        gex_data.append({"strike": strike, "gex": gex, "type": "put", "oi": oi})

    if not gex_data:
        return None

    df = pd.DataFrame(gex_data)
    strike_gex = df.groupby("strike").agg({"gex": "sum", "oi": "sum"}).reset_index()

    positive_wall = strike_gex[strike_gex["gex"] > 0].nlargest(1, "gex")
    negative_wall = strike_gex[strike_gex["gex"] < 0].nsmallest(1, "gex")

    nearby_range = current_price * 0.03
    nearby_gex = strike_gex[
        (strike_gex["strike"] >= current_price - nearby_range)
        & (strike_gex["strike"] <= current_price + nearby_range)
    ]["gex"].sum()

    return {
        "ticker": ticker,
        "current_price": current_price,
        "strike_gex": strike_gex.to_dict("records"),
        "positive_wall": positive_wall.iloc[0].to_dict()
        if len(positive_wall) > 0
        else None,
        "negative_wall": negative_wall.iloc[0].to_dict()
        if len(negative_wall) > 0
        else None,
        "nearby_net_gex": nearby_gex,
        "total_gex": strike_gex["gex"].sum(),
    }


def calculate_max_pain(
    ticker: str = "",
    *,
    calls: Optional[pd.DataFrame] = None,
    puts: Optional[pd.DataFrame] = None,
) -> Optional[float]:
    """Max Pain (最もオプション価値が失効するストライク価格) を計算"""
    if calls is None or puts is None:
        option_data = get_option_chain(ticker)
        if option_data is None:
            return None
        calls, puts = option_data

    strikes = sorted(set(calls["strike"].tolist() + puts["strike"].tolist()))
    loss_data = []

    for k in strikes:
        call_loss = (
            calls[calls["strike"] < k]
            .apply(lambda r: (k - r["strike"]) * r["openInterest"], axis=1)
            .sum()
        )
        put_loss = (
            puts[puts["strike"] > k]
            .apply(lambda r: (r["strike"] - k) * r["openInterest"], axis=1)
            .sum()
        )
        loss_data.append({"strike": k, "loss": call_loss + put_loss})

    if not loss_data:
        return None
    df = pd.DataFrame(loss_data)
    return df.loc[df["loss"].idxmin()]["strike"]


def calculate_atm_iv(
    ticker: str = "",
    *,
    calls: Optional[pd.DataFrame] = None,
    puts: Optional[pd.DataFrame] = None,
    current_price: float = 0.0,
) -> Optional[float]:
    """ATM (At The Money) の平均IVを計算"""
    if calls is None or puts is None or current_price == 0.0:
        fetched = _fetch_option_data(ticker)
        if fetched is None:
            return None
        calls, puts, current_price = fetched

    nearby_calls = calls[
        (calls["strike"] >= current_price * 0.98)
        & (calls["strike"] <= current_price * 1.02)
    ]
    nearby_puts = puts[
        (puts["strike"] >= current_price * 0.98)
        & (puts["strike"] <= current_price * 1.02)
    ]

    ivs = (
        nearby_calls["impliedVolatility"].tolist()
        + nearby_puts["impliedVolatility"].tolist()
    )
    valid_ivs = []
    for iv in ivs:
        if iv is None or iv == 0:
            continue
        # Finnhubは百分率(例: 15.56)、yfinanceは小数(例: 0.1556)で返す
        if iv > 2:
            iv = iv / 100.0
        if 0 < iv < 2:
            valid_ivs.append(iv)

    if not valid_ivs:
        return None
    return sum(valid_ivs) / len(valid_ivs)


# ============================================================
# 統合分析（データを1回取得し、各関数に渡す）
# ============================================================


def analyze_option_sentiment(ticker: str) -> Optional[dict]:
    """
    オプションセンチメント分析を行います。
    option_chain と quote を1回だけ取得し、全計算に共有します。

    Args:
        ticker: 銘柄コード

    Returns:
        センチメント分析結果
    """
    # === データ取得（1回のみ） ===
    fetched = _fetch_option_data(ticker)
    if fetched is None:
        return None
    calls, puts, current_price = fetched

    # === 各指標を事前取得済みデータで計算 ===
    pcr = calculate_pcr(ticker, calls=calls, puts=puts)
    gex = calculate_gex(ticker, calls=calls, puts=puts, current_price=current_price)
    iv = calculate_atm_iv(ticker, calls=calls, puts=puts, current_price=current_price)
    max_pain = calculate_max_pain(ticker, calls=calls, puts=puts)

    if pcr is None and gex is None:
        return None

    # OIが極端に少ない場合はGEXの信頼性が低い
    if pcr and (pcr["total_call_oi"] + pcr["total_put_oi"] < 1000):
        gex = None

    sentiment = "中立"
    analysis = []

    if pcr:
        vol_pcr = pcr["volume_pcr"]
        if vol_pcr > 1.2:
            sentiment = "弱気"
            analysis.append(
                f"PCR(Vol) ({vol_pcr:.2f}) が高く、プット取引活発 (弱気示唆)"
            )
        elif vol_pcr < 0.7:
            sentiment = "強気"
            analysis.append(
                f"PCR(Vol) ({vol_pcr:.2f}) が低く、コール取引活発 (強気示唆)"
            )
        else:
            analysis.append(f"PCR(Vol) ({vol_pcr:.2f}) は中立水準")

        if gex is None:
            analysis.append("※ OIデータ不足のためGEX分析は省略")

    if gex:
        if gex["nearby_net_gex"] > 0:
            analysis.append("近傍GEX: 正 (値動き抑制)")
        else:
            analysis.append("近傍GEX: 負 (ボラ拡大警戒)")

        if gex["positive_wall"]:
            analysis.append(f"+Wall (${gex['positive_wall']['strike']:.0f}): 上値抵抗")
        if gex["negative_wall"]:
            analysis.append(f"-Wall (${gex['negative_wall']['strike']:.0f}): 下値支持")

    if iv:
        analysis.append(f"ATM IV: {iv:.1%}")

    if max_pain:
        analysis.append(f"Max Pain: ${max_pain:.0f}")

    return {
        "ticker": ticker,
        "current_price": current_price,
        "sentiment": sentiment,
        "pcr": pcr,
        "gex": gex,
        "iv": iv,
        "max_pain": max_pain,
        "analysis": analysis,
    }


def get_major_indices_options(market_type: str = "US") -> list[dict]:
    """
    主要指数ETF (SPY, QQQ, IWM) のオプション分析を取得します。
    日本市場ではオプションデータが取得できないため空リストを返します。

    Args:
        market_type: "US" または "JP"

    Returns:
        各指数のオプション分析結果のリスト（日本市場では空）
    """
    if market_type == "JP":
        return []

    indices = ["SPY", "QQQ", "IWM"]
    results = []

    for ticker in indices:
        analysis = analyze_option_sentiment(ticker)
        if analysis:
            results.append(analysis)

    return results
