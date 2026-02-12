"""
オプション分析モジュール
GEX (Gamma Exposure)、PCR (Put/Call Ratio)、Gamma Wallの計算を行います。
"""
import pandas as pd
import numpy as np
from scipy.stats import norm
from typing import Optional
from .market_data import get_option_chain
from .finnhub_client import get_quote, is_configured


def calculate_pcr(ticker: str) -> Optional[dict]:
    """
    Put/Call Ratioを計算します。
    
    Args:
        ticker: 銘柄コード (SPY, QQQ, IWM)
    
    Returns:
        PCR情報の辞書
    """
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


def calculate_gex(ticker: str) -> Optional[dict]:
    """
    Gamma Exposure (GEX) を計算します。
    
    Args:
        ticker: 銘柄コード
    
    Returns:
        GEX情報の辞書（ストライク別GEXとWall情報を含む）
    """
    option_data = get_option_chain(ticker)
    if option_data is None:
        return None
    
    calls, puts = option_data
    
    # 現在の株価を取得 (Finnhub)
    quote = get_quote(ticker)
    if not quote or quote.get("c", 0) == 0:
        return None
    current_price = quote["c"]
    
    # GEX計算用のデータ準備
    gex_data = []
    
    # Callsの処理
    for _, row in calls.iterrows():
        strike = row.get("strike", 0)
        oi = row.get("openInterest", 0)
        gamma = row.get("gamma", 0)
        
        if pd.isna(gamma) or gamma == 0:
            # Gammaが提供されていない場合はBlack-Scholesで推定
            # 簡易版: ATMに近いほど高く、離れるほど低くなる近似
            moneyness = abs(strike - current_price) / current_price
            gamma = max(0.001, 0.05 * np.exp(-5 * moneyness))  # ATMで約0.05、離れると減衰
        
        # Call GEX: positive (ディーラーはロングガンマ)
        gex = gamma * oi * 100 * current_price
        gex_data.append({
            "strike": strike,
            "gex": gex,
            "type": "call",
            "oi": oi
        })
    
    # Putsの処理
    for _, row in puts.iterrows():
        strike = row.get("strike", 0)
        oi = row.get("openInterest", 0)
        gamma = row.get("gamma", 0)
        
        if pd.isna(gamma) or gamma == 0:
            moneyness = abs(strike - current_price) / current_price
            gamma = max(0.001, 0.05 * np.exp(-5 * moneyness))
        
        # Put GEX: negative (ディーラーはショートガンマ)
        gex = -gamma * oi * 100 * current_price
        gex_data.append({
            "strike": strike,
            "gex": gex,
            "type": "put",
            "oi": oi
        })
    
    if not gex_data:
        return None
    
    df = pd.DataFrame(gex_data)
    
    # ストライク別にGEXを集計
    strike_gex = df.groupby("strike").agg({
        "gex": "sum",
        "oi": "sum"
    }).reset_index()
    
    # Gamma Wallの特定
    positive_wall = strike_gex[strike_gex["gex"] > 0].nlargest(1, "gex")
    negative_wall = strike_gex[strike_gex["gex"] < 0].nsmallest(1, "gex")
    
    # 現在価格近傍のネットGEX
    nearby_range = current_price * 0.03  # ±3%
    nearby_gex = strike_gex[
        (strike_gex["strike"] >= current_price - nearby_range) &
        (strike_gex["strike"] <= current_price + nearby_range)
    ]["gex"].sum()
    
    return {
        "ticker": ticker,
        "current_price": current_price,
        "strike_gex": strike_gex.to_dict("records"),
        "positive_wall": positive_wall.iloc[0].to_dict() if len(positive_wall) > 0 else None,
        "negative_wall": negative_wall.iloc[0].to_dict() if len(negative_wall) > 0 else None,
        "nearby_net_gex": nearby_gex,
        "total_gex": strike_gex["gex"].sum(),
    }


def calculate_max_pain(ticker: str) -> Optional[float]:
    """Max Pain (最もオプション価値が失効するストライク価格) を計算"""
    option_data = get_option_chain(ticker)
    if option_data is None: return None
    calls, puts = option_data
    
    strikes = sorted(list(set(calls["strike"].tolist() + puts["strike"].tolist())))
    loss_data = []
    
    for k in strikes:
        call_loss = calls[calls["strike"] < k].apply(
            lambda r: (k - r["strike"]) * r["openInterest"], axis=1
        ).sum()
        put_loss = puts[puts["strike"] > k].apply(
            lambda r: (r["strike"] - k) * r["openInterest"], axis=1
        ).sum()
        loss_data.append({"strike": k, "loss": call_loss + put_loss})
        
    if not loss_data: return None
    df = pd.DataFrame(loss_data)
    max_pain = df.loc[df["loss"].idxmin()]["strike"]
    return max_pain


def calculate_atm_iv(ticker: str) -> Optional[float]:
    """ATM (At The Money) の平均IVを計算"""
    # 現在の株価を取得 (Finnhub)
    quote = get_quote(ticker)
    if not quote or quote.get("c", 0) == 0:
        return None
    current_price = quote["c"]
    
    option_data = get_option_chain(ticker)
    if option_data is None: return None
    calls, puts = option_data
    
    # 現在価格に近いストライク (±2%)
    nearby_calls = calls[
        (calls["strike"] >= current_price * 0.98) & 
        (calls["strike"] <= current_price * 1.02)
    ]
    nearby_puts = puts[
        (puts["strike"] >= current_price * 0.98) & 
        (puts["strike"] <= current_price * 1.02)
    ]
    
    ivs = nearby_calls["impliedVolatility"].tolist() + nearby_puts["impliedVolatility"].tolist()
    # 0や異常値を除外
    valid_ivs = [iv for iv in ivs if iv is not None and 0 < iv < 2]
    
    if not valid_ivs: return None
    return sum(valid_ivs) / len(valid_ivs)


def analyze_option_sentiment(ticker: str) -> Optional[dict]:
    """
    オプションセンチメント分析を行います。
    
    Args:
        ticker: 銘柄コード
    
    Returns:
        センチメント分析結果（current_price, sentiment, pcr, gex, iv, max_pain, analysis を含む辞書）
    """
    pcr = calculate_pcr(ticker)
    gex = calculate_gex(ticker)
    iv = calculate_atm_iv(ticker)
    max_pain = calculate_max_pain(ticker)
    
    if pcr is None and gex is None:
        return None
    
    # 現在価格: GEXから取得、なければ直接取得
    current_price = 0.0
    if gex and gex.get("current_price"):
        current_price = gex["current_price"]
    else:
        quote = get_quote(ticker)
        if quote and quote.get("c", 0) != 0:
            current_price = quote["c"]
    
    sentiment = "中立"
    analysis = []
    
    # OIベースのPCRは信頼性が低いため（yfinance制限）、Volumeベースを採用する
    # しかし、元々の関数は両方返している。ここで「使用するPCR」を決定する。
    
    # GEXはOI必須のため、OIが極端に少ない場合は信頼できないとしてNoneにする
    # 簡易判定: PCR情報の total_put_oi + total_call_oi が少なすぎる場合
    if pcr and (pcr["total_call_oi"] + pcr["total_put_oi"] < 1000):
        gex = None # 強制無効化
        
    sentiment = "中立"
    analysis = []
    
    if pcr:
        # Volume PCRを主指標とする
        vol_pcr = pcr["volume_pcr"]
        if vol_pcr > 1.2:
            sentiment = "弱気"
            analysis.append(f"PCR(Vol) ({vol_pcr:.2f}) が高く、プット取引活発 (弱気示唆)")
        elif vol_pcr < 0.7:
            sentiment = "強気"
            analysis.append(f"PCR(Vol) ({vol_pcr:.2f}) が低く、コール取引活発 (強気示唆)")
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
    # 日本市場ではオプションデータ取得不可
    if market_type == "JP":
        return []
    
    indices = ["SPY", "QQQ", "IWM"]
    results = []
    
    for ticker in indices:
        analysis = analyze_option_sentiment(ticker)
        if analysis:
            results.append(analysis)
    
    return results
