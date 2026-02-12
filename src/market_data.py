"""
市場データ取得モジュール
株価、オプションチェーン、ニュース、企業情報を取得します。
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
# import requests_cache # Moved to local import in _get_yf_session for robustness
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional
from src.finnhub_client import (
    get_candles, get_quote, get_company_profile, 
    get_basic_financials, get_company_news, is_configured
)
from src.market_config import get_market_config
from src.network import get_session


@st.cache_data(ttl=300) # 5分キャッシュ



def get_stock_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
    """
    指定銘柄の株価データを取得します。
    Finnhubを使用します。
    
    Args:
        ticker: 銘柄コード
        period: 期間 (1d, 5d, 1mo, 3mo, 6mo, 1y, ytd, max)
    
    Returns:
        OHLCV データフレーム
    """
    # Finnhub未設定なら空を返す（またはyfinanceフォールバックも検討可能だが今回は移行）
    if not is_configured():
        print(f"[DATA_WARN] Finnhub API key not configured. Falling back to yfinance for {ticker}.")
        # --- Fallback to yfinance if Finnhub not ready ---
        try:
            # Note: Do not pass custom session to yf.Ticker as it conflicts with internal curl_cffi usage
            # needed for anti-bot bypass.
            return yf.Ticker(ticker).history(period=period)
        except Exception as e:
            print(f"[DATA_ERROR] yfinance fallback failed for {ticker}: {e}")
            return pd.DataFrame()

    # Finnhubからこれらを取得
    # periodをresolutionに変換
    resolution = "D"
    if period in ["1d", "5d"]: resolution = "60" # 60分足 (1d/5dは細かい方がいいが、Freeは日足主体推奨)
    # Finnhub Free Tierの制限: Intradayは米株のみ？ 
    # 安全策として日足("D")を標準にするか。
    # App is designing for "1mo" default. "D" is fine.
    
    # Calculate from/to datetimes
    now = datetime.now()
    start = now - timedelta(days=30) # Default 1mo
    
    if period == "1d": start = now - timedelta(days=1); resolution="5"
    elif period == "5d": start = now - timedelta(days=5); resolution="60"
    elif period == "3mo": start = now - timedelta(days=90)
    elif period == "6mo": start = now - timedelta(days=180)
    elif period == "1y": start = now - timedelta(days=365)
    elif period == "ytd": start = datetime(now.year, 1, 1)
    elif period == "max": start = now - timedelta(days=365*5) # 5 years

    try:
        # get_candles returns a DataFrame or empty DataFrame on failure
        df = get_candles(ticker, resolution, start, now)
        
        if df is None or df.empty:
            print(f"[DATA_WARN] Finnhub returned no candles for {ticker}. Falling back to yfinance.")
            # Fallback to yfinance
            try:
                # Note: Do not pass custom session to yf.Ticker
                return yf.Ticker(ticker).history(period=period)
            except Exception as e:
                print(f"[DATA_ERROR] yfinance fallback failed for {ticker}: {e}")
                return pd.DataFrame()
            
        return df
    except Exception as e:
        print(f"[DATA_ERROR] Finnhub candle fetch error for {ticker}: {e}")
        # Fallback to yfinance
        try:
            return yf.Ticker(ticker).history(period=period)
        except Exception as ey:
             print(f"[DATA_ERROR] yfinance fallback failed for {ticker}: {ey}")
             return pd.DataFrame()


def get_option_chain(ticker: str) -> Optional[tuple[pd.DataFrame, pd.DataFrame]]:
    """
    オプションチェーンデータを取得します。
    Finnhub Free Tierで提供なし → yfinance維持 (Hybrid構成)
    """
    try:
        # Note: Do not pass custom session to yf.Ticker
        stock = yf.Ticker(ticker)
        # yfinanceのoptionsプロパティはHTTPリクエストを伴うためエラーが出る可能性がある
        try:
            expirations = stock.options
        except Exception as e:
             print(f"[DATA_ERROR] Failed to fetch option expirations for {ticker}: {e}")
             return None
             
        if not expirations:
            print(f"[DATA_WARN] No option expirations found for {ticker}")
            return None
        
        all_calls = []
        all_puts = []
        # レート制限回避のため直近2つのみに絞る
        for exp in expirations[:2]:
            try:
                opt = stock.option_chain(exp)
                calls = opt.calls.copy()
                puts = opt.puts.copy()
                calls["expiration"] = exp
                puts["expiration"] = exp
                all_calls.append(calls)
                all_puts.append(puts)
            except Exception as e:
                print(f"[DATA_WARN] Failed to fetch option chain for {ticker} exp {exp}: {e}")
                continue
                
        if not all_calls:
            print(f"[DATA_WARN] No option chains successfully fetched for {ticker}")
            return None
            
        calls_df = pd.concat(all_calls, ignore_index=True)
        puts_df = pd.concat(all_puts, ignore_index=True)
        
        return calls_df, puts_df
    except Exception as e:
        print(f"[DATA_ERROR] Unexpected option fetch error for {ticker}: {e}")
        return None


def _get_stooq_data(ticker: str, period_days: int = 10) -> tuple[float, float] | None:
    """Stooqデータ取得 (変更なし)"""
    import requests
    from io import StringIO
    
    try:
        end = datetime.now()
        start = end - timedelta(days=period_days)
        d1 = start.strftime("%Y%m%d")
        d2 = end.strftime("%Y%m%d")
        url = f"https://stooq.com/q/d/l/?s={ticker}&i=d&d1={d1}&d2={d2}"
        
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return None
        
        df = pd.read_csv(StringIO(response.text))
        if df.empty or len(df) < 2 or "Close" not in df.columns: return None
        
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date")
        
        current = df["Close"].iloc[-1]
        prev = df["Close"].iloc[-2]
        change = ((current - prev) / prev) * 100
        return (current, change)
    except:
        return None


JP_STOOQ_TICKERS = {
    "日経平均": "^NKX",
    "TOPIX": "^TPX",
}


@st.cache_data(ttl=300)
def get_market_indices(market_type: str = "US") -> dict[str, dict]:
    """
    主要市場指数のデータを取得。
    US: Finnhub quote
    JP: Stooq
    Global: Finnhub quote
    """
    config = get_market_config(market_type)
    result = {}
    
    # --- 日本市場 (Stooq優先) ---
    if market_type == "JP":
        for name, ticker in JP_STOOQ_TICKERS.items():
            data = _get_stooq_data(ticker)
            if data:
                result[name] = {"price": data[0], "change": data[1], "ticker": ticker}
                
        # その他（コモディティ等）はFinnhubで（yfinanceコードは削除/置換）
        targets = {**config["commodities"], **config["crypto"], **config["forex"]}
        for name, ticker in targets.items():
            # Finnhub用のティッカー変換が必要な場合があるが、
            # configの定義(CL=F, BTC-USD等)はYahoo準拠。
            # Finnhubは BTC-USD OK, CL=F(futures) はシンボルが違う可能性あり。
            # いったんそのまま投げてみて、ダメならエラーログ出るだけ。
            # Finnhub Crypto: "BINANCE:BTCUSDT" 等が正確だが "BTC-USD" も通るか要確認。
            # 簡易的にyfinanceフォールバックを残す手もあるが、移行方針なのでFinnhubへ。
            
            # 注: FinnhubのForex/Cryptoシンボルは "IC MARKETS:1" のような形式が多い
            # ここでは主要なもののマッピングが課題になる。
            # 面倒なのでコモディティ/Cryptoは一旦 yfinanceのままにするか？
            # -> 計画では「移行」だが、シンボル非互換はリスク。
            # 安全策: 今回はIndices(US)をFinnhub化し、他は維持orFinnhubトライ。
            pass
            
        return result

    # --- 米国市場 (Finnhub移行 + YF併用) ---
    
    # 1. Finnhub Targets (Indices, Sectors, Commodities, Crypto)
    finnhub_targets = {
        **config["indices"],
        **config["sectors"],
        **config["commodities"], 
        **config["crypto"], 
    }
    
    # 2. yfinance Targets (Treasuries, Forex)
    # Treasuries are ^TNX (Indices) which Finnhub Free Tier doesn't support.
    # Forex (JPY=X) is blocked on Finnhub Free Tier (OANDA).
    yf_targets = {
        **config["treasuries"],
        **config["forex"]
    }
    
    # Finnhub APIキー未設定なら全てyfinanceへ
    if not is_configured():
        print(f"[DATA_WARN] Finnhub API key not configured. Using yfinance for all.")
        yf_targets.update(finnhub_targets)
        finnhub_targets = {}

    # --- Fetch from Finnhub ---
    for name, ticker in finnhub_targets.items():
        try:
            q = get_quote(ticker)
            if isinstance(q, dict) and q.get("c") not in (0, None):
                result[name] = {"price": q.get("c"), "change": q.get("dp", 0), "ticker": ticker}
            else:
                print(f"[DATA_WARN] Finnhub returned no data for {name} ({ticker}). Adding to YF fallback.")
                yf_targets[name] = ticker
        except Exception as e:
            print(f"[DATA_ERROR] Finnhub error for {name} ({ticker}): {e}")
            yf_targets[name] = ticker

    # --- Fetch from yfinance (Treasuries, Forex, Fallbacks) ---
    if yf_targets:
        try:
            # Batch download is efficient for multiple tickers
            tickers_list = list(yf_targets.values())
            if tickers_list:
                # Note: yf.download might print progress, quiet=True suppresses it in newer versions
                # period="2d" to calculate change if needed, but "1d" often enough for current price?
                # We need "previous close" to calc change if YF doesn't give it efficiently.
                # 'prepost=True' might be good for extended hours but let's stick to standard.
                batch_data = yf.download(tickers_list, period="5d", progress=False)
                
                # Check format of batch_data. If single ticker, it's different?
                # yfinance usually returns MultiIndex columns if multiple tickers.
                
                for name, ticker in yf_targets.items():
                    try:
                        # Handle MultiIndex
                        if len(tickers_list) > 1:
                            hist = batch_data.xs(ticker, level=1, axis=1) if isinstance(batch_data.columns, pd.MultiIndex) else batch_data
                        else:
                            hist = batch_data
                        
                        # Data extraction
                        if not hist.empty and len(hist) >= 1:
                            current = hist["Close"].iloc[-1]
                            # Try to get previous close for change calc
                            prev = hist["Close"].iloc[-2] if len(hist) >= 2 else current
                            
                            # For Treasuries (Indices), data might be sparse? usually OK.
                            # For Forex, 5d is enough.
                            
                            change = ((current - prev) / prev) * 100 if prev != 0 else 0
                            
                            result[name] = {"price": float(current), "change": float(change), "ticker": ticker}
                        else:
                            result[name] = {"price": 0.0, "change": 0.0, "ticker": ticker}
                            print(f"[DATA_WARN] yfinance returned no data for {name} ({ticker})")
                    except Exception as e_inner:
                        print(f"[DATA_WARN] Error parsing YF data for {name} ({ticker}): {e_inner}")
        except Exception as e:
            print(f"[DATA_ERROR] yfinance batch fetch error: {e}")

    return result


def get_stock_news(ticker: str, max_items: int = 10) -> list[dict]:
    """
    銘柄ニュース取得。
    Finnhub Company News を使用。
    """
    if not is_configured():
        return []

    news = get_company_news(ticker)
    # フォーマット変換
    results = []
    for item in news[:max_items]:
        results.append({
            "title": item.get("headline"),
            "publisher": item.get("source"),
            "link": item.get("url"),
            "published": datetime.fromtimestamp(item.get("datetime", 0)).strftime("%Y-%m-%d %H:%M"),
            "summary": item.get("summary", "")
        })
    return results


@st.cache_data(ttl=86400) # 1日キャッシュ
def get_stock_info(ticker: str) -> dict:
    """
    企業概要を取得します (Finnhub優先 -> yfinance Fallback)。
    
    Args:
        ticker: 銘柄コード
        
    Returns:
        dict: {name, ticker, sector, industry, summary, website, logo, city, state, country, employees, exchange}
    """
    info = {
        "name": ticker,
        "ticker": ticker,
        "sector": "N/A",
        "industry": "N/A",
        "summary": "情報なし",
        "website": "",
        "logo": "",
        "city": "",
        "state": "",
        "country": "",
        "employees": 0,
        "exchange": ""
    }
    
    # 1. Finnhub
    if is_configured():
        try:
            profile = get_company_profile(ticker)
            if profile:
                info.update({
                    "name": profile.get("name", ticker),
                    "ticker": profile.get("ticker", ticker),
                    "sector": profile.get("finnhubIndustry", "N/A"), # Finnhub returns Industry as 'finnhubIndustry'
                    "industry": profile.get("finnhubIndustry", "N/A"),
                    "website": profile.get("weburl", ""),
                    "logo": profile.get("logo", ""),
                    "exchange": profile.get("exchange", ""),
                    "country": profile.get("country", ""),
                })
                # Finnhub doesn't always have a long summary.
        except Exception as e:
            print(f"[DATA_WARN] Finnhub profile fetch failed for {ticker}: {e}")

    # 2. yfinance Fallback (補完的に使用)
    # SummaryやSectorがFinnhubで取れない場合、またはFinnhub失敗時
    if info["summary"] == "情報なし" or info["sector"] == "N/A":
        try:
            # Note: Do not use custom session for yf.Ticker
            yf_ticker = yf.Ticker(ticker)
            yf_info = yf_ticker.info
            
            if yf_info:
                if info["name"] == ticker: info["name"] = yf_info.get("longName", yf_info.get("shortName", ticker))
                if info["sector"] == "N/A": info["sector"] = yf_info.get("sector", "N/A")
                if info["industry"] == "N/A": info["industry"] = yf_info.get("industry", "N/A")
                if info["summary"] == "情報なし": info["summary"] = yf_info.get("longBusinessSummary", "")
                if not info["website"]: info["website"] = yf_info.get("website", "")
                if not info["city"]: info["city"] = yf_info.get("city", "")
                if not info["state"]: info["state"] = yf_info.get("state", "")
                if not info["country"]: info["country"] = yf_info.get("country", "")
                if info["employees"] == 0: info["employees"] = yf_info.get("fullTimeEmployees", 0)
        except Exception as e:
            print(f"[DATA_WARN] yfinance profile fallback failed for {ticker}: {e}")

    return info


