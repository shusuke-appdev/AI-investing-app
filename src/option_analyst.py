"""
オプション分析モジュール
GEX (Gamma Exposure)、PCR (Put/Call Ratio)、Gamma Wallの計算を行います。
Finnhub APIから取得したGreeksを活用し、より正確な分析を提供します。
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .data_provider import DataProvider
from .log_config import get_logger
from .market_data import get_option_chain

logger = get_logger(__name__)

# ============================================================
# 内部ヘルパー: データ取得（1回だけ実行）
# ============================================================


def _fetch_option_data(
    ticker: str,
) -> tuple[pd.DataFrame, pd.DataFrame, float] | None:
    """
    オプションチェーンと現在価格を1回で取得する内部ヘルパー。

    Returns:
        (calls_df, puts_df, current_price, fetched_at) のタプル、またはNone
    """
    option_data = get_option_chain(ticker)
    if option_data is None:
        return None

    calls, puts = option_data

    # 現在価格取得（DataProvider経由: Finnhub→yfinanceフォールバック内蔵）
    # Note: timestamp is not directly returned by get_current_price, so we use current time
    # Strictly speaking we should get time from quote, but for now system time is enough for "freshness" check
    # to show user when THIS analysis was run.
    # Cloud environment often uses UTC, so we convert to JST explicitly.
    current_price = DataProvider.get_current_price(ticker)

    JST = timezone(timedelta(hours=9), "JST")
    now_utc = datetime.now(timezone.utc)
    now_jst = now_utc.astimezone(JST)
    now_str = now_jst.strftime("%Y/%m/%d %H:%M:%S") + " (JST)"

    if not current_price:
        return None

    return calls, puts, current_price, now_str


# ============================================================
# 個別計算関数（データを引数で受け取る版 + 後方互換のticker版）
# ============================================================


def calculate_pcr(
    ticker: str = "",
    *,
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
) -> dict | None:
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
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
    current_price: float = 0.0,
) -> dict | None:
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
        calls, puts, current_price, _ = fetched

    total_oi = calls["openInterest"].sum() + puts["openInterest"].sum()
    if total_oi == 0:
        logger.warning(f"[OptionAnalyst] {ticker}: OpenInterest is 0. Cannot calculate GEX.")
        return None

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
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
) -> float | None:
    """Max Pain (最もオプション価値が失効するストライク価格) を計算"""
    if calls is None or puts is None:
        option_data = get_option_chain(ticker)
        if option_data is None:
            return None
        calls, puts = option_data

    # 建玉データがない場合のフォールバック（週末などのyfinance不具合対策）
    total_oi = calls["openInterest"].sum() + puts["openInterest"].sum()
    use_vol = total_oi == 0
    total_vol = 0
    if use_vol and "volume" in calls.columns and "volume" in puts.columns:
        total_vol = calls["volume"].fillna(0).sum() + puts["volume"].fillna(0).sum()
        if total_vol > 0:
            logger.warning(f"[OptionAnalyst] {ticker}: OpenInterest is 0. Falling back to Volume for Max Pain.")

    if total_oi == 0 and total_vol == 0:
        logger.warning(f"[OptionAnalyst] {ticker}: No valid OI or Volume data. Cannot calculate Max Pain.")
        return None

    weight_col = "volume" if use_vol else "openInterest"

    # NaNを0で埋めて計算可能な状態にする
    calls_clean = calls.copy()
    puts_clean = puts.copy()
    if weight_col in calls_clean.columns:
        calls_clean[weight_col] = calls_clean[weight_col].fillna(0)
    else:
        calls_clean[weight_col] = 0

    if weight_col in puts_clean.columns:
        puts_clean[weight_col] = puts_clean[weight_col].fillna(0)
    else:
        puts_clean[weight_col] = 0

    strikes = sorted(set(calls_clean["strike"].tolist() + puts_clean["strike"].tolist()))
    loss_data = []

    for k in strikes:
        call_loss = (
            calls_clean[calls_clean["strike"] < k]
            .apply(lambda r, current_k=k: (current_k - r["strike"]) * r[weight_col], axis=1)
            .sum()
        )
        put_loss = (
            puts_clean[puts_clean["strike"] > k]
            .apply(lambda r, current_k=k: (r["strike"] - current_k) * r[weight_col], axis=1)
            .sum()
        )
        loss_data.append({"strike": k, "loss": call_loss + put_loss})

    if not loss_data:
        return None

    df = pd.DataFrame(loss_data)

    # 全ての loss が 0 または同一値（計算不能状態）の場合は None を返す
    if df["loss"].nunique() <= 1 or df["loss"].sum() == 0:
        logger.warning(f"[OptionAnalyst] {ticker}: All strike losses are identical or zero. Returning None.")
        return None

    return float(df.loc[df["loss"].idxmin()]["strike"])


def calculate_atm_iv(
    ticker: str = "",
    *,
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
    current_price: float = 0.0,
) -> float | None:
    """ATM (At The Money) の平均IVを計算"""
    if calls is None or puts is None or current_price == 0.0:
        fetched = _fetch_option_data(ticker)
        if fetched is None:
            return None
        calls, puts, current_price, _ = fetched

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


def calculate_skew(
    ticker: str = "",
    *,
    calls: pd.DataFrame | None = None,
    puts: pd.DataFrame | None = None,
    current_price: float = 0.0,
) -> float | None:
    """
    OTM Put IVとOTM Call IVの差からスキュー(Skew)を計算します。
    正の値は下落リスク（Putの割高感）を、負の値は上昇リスクを強く織り込んでいることを示します。
    """
    if calls is None or puts is None or current_price == 0.0:
        fetched = _fetch_option_data(ticker)
        if fetched is None:
            return None
        calls, puts, current_price, _ = fetched

    if puts.empty or calls.empty:
        return None

    # 10% OTMのストライクを目安に
    target_put_strike = current_price * 0.90
    target_call_strike = current_price * 1.10

    # 有効なIVを持つデータに絞る
    valid_puts = puts[puts["impliedVolatility"] > 0]
    valid_calls = calls[calls["impliedVolatility"] > 0]

    if valid_puts.empty or valid_calls.empty:
        return None

    # putはstrike <= current_price のOTM
    otm_puts = valid_puts[valid_puts["strike"] <= current_price]
    if otm_puts.empty:
        return None
    otm_put = otm_puts.iloc[(otm_puts["strike"] - target_put_strike).abs().argmin()]

    # callはstrike >= current_price のOTM
    otm_calls = valid_calls[valid_calls["strike"] >= current_price]
    if otm_calls.empty:
        return None
    otm_call = otm_calls.iloc[(otm_calls["strike"] - target_call_strike).abs().argmin()]

    put_iv = otm_put["impliedVolatility"]
    call_iv = otm_call["impliedVolatility"]

    # yfinance(小数)とFinnhub(パーセンテージ)のスケール吸収
    if put_iv > 2:
        put_iv /= 100.0
    if call_iv > 2:
        call_iv /= 100.0

    return put_iv - call_iv


def estimate_price_range(
    current_price: float, atm_iv: float, days_to_expiry: float = 30.0
) -> tuple[float, float]:
    """
    IVと期間(DTE)から1標準偏差(約68%)の予想変動レンジを算出します。

    Returns:
        (lower_bound, upper_bound)
    """
    if atm_iv is None or atm_iv <= 0:
        return current_price, current_price

    # 予想変動率 = IV * sqrt(DTE / 365)
    expected_move_pct = atm_iv * np.sqrt(max(1.0, days_to_expiry) / 365.0)

    lower_bound = current_price * (1.0 - expected_move_pct)
    upper_bound = current_price * (1.0 + expected_move_pct)

    return lower_bound, upper_bound


# ============================================================
# 統合分析（データを1回取得し、各関数に渡す）
# ============================================================


def analyze_option_sentiment(ticker: str) -> dict | None:
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
    calls, puts, current_price, fetched_at = fetched

    # === 各指標を事前取得済みデータで計算 ===
    pcr = calculate_pcr(ticker, calls=calls, puts=puts)
    gex = calculate_gex(ticker, calls=calls, puts=puts, current_price=current_price)
    iv = calculate_atm_iv(ticker, calls=calls, puts=puts, current_price=current_price)
    max_pain = calculate_max_pain(ticker, calls=calls, puts=puts)
    skew = calculate_skew(ticker, calls=calls, puts=puts, current_price=current_price)

    # DTE (Days to Expiry) 計算
    dte = 30.0
    if not calls.empty and "expiration" in calls.columns:
        exp_date_str = calls["expiration"].iloc[0]
        try:
            exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            now_utc = datetime.now(timezone.utc)
            dte = max(1.0, (exp_date - now_utc).days)
        except Exception:
            pass

    price_range = None
    if iv:
        price_range = estimate_price_range(current_price, iv, dte)

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
        if price_range:
            lower, upper = price_range
            analysis.append(
                f"予想レンジ(1σ, {int(dte)}日): ${lower:.2f} - ${upper:.2f}"
            )

    if skew is not None:
        if skew > 0.05:
            analysis.append(f"Skew: {skew:.1%} (下落警戒強め)")
        elif skew < -0.05:
            analysis.append(f"Skew: {skew:.1%} (上昇警戒強め)")
        else:
            analysis.append(f"Skew: {skew:.1%} (中立水準)")

    if max_pain:
        analysis.append(f"Max Pain: ${max_pain:.0f}")

    return {
        "ticker": ticker,
        "current_price": current_price,
        "sentiment": sentiment,
        "pcr": pcr,
        "gex": gex,
        "iv": iv,
        "skew": skew,
        "dte": dte,
        "price_range": price_range,
        "max_pain": max_pain,
        "analysis": analysis,
        "fetched_at": fetched_at,
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
