"""
市場データ取得モジュール
株価、オプションチェーン、ニュース、企業情報を取得します。
"""
import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=100)
def get_stock_data(ticker: str, period: str = "1mo") -> pd.DataFrame:
    """
    指定銘柄の株価データを取得します。
    
    Args:
        ticker: 銘柄コード
        period: 期間 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    
    Returns:
        OHLCV データフレーム
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()


def get_multiple_stocks_data(tickers: list[str], period: str = "1mo") -> dict[str, pd.DataFrame]:
    """
    複数銘柄の株価データを一括取得します。
    
    Args:
        tickers: 銘柄コードのリスト
        period: 期間
    
    Returns:
        銘柄コードをキーとするデータフレームの辞書
    """
    result = {}
    for ticker in tickers:
        result[ticker] = get_stock_data(ticker, period)
    return result


def get_stock_info(ticker: str) -> dict:
    """
    銘柄の企業情報を取得します。
    
    Args:
        ticker: 銘柄コード
    
    Returns:
        企業情報の辞書 (name, sector, industry, summary, etc.)
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 現在価格を取得
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        if not current_price:
            try:
                hist = stock.history(period="1d")
                current_price = hist["Close"].iloc[-1] if not hist.empty else 0
            except Exception:
                current_price = 0
        


        # 追加指標の取得と補正
        
        # 配当利回りの補正 (dividendRateがあれば優先)
        div_yield = info.get("dividendYield", None)
        div_rate = info.get("dividendRate", None)
        if div_rate and current_price and current_price > 0:
             # dividendYieldがNoneまたは異常値(>0.2: 20%)の場合、Rateから再計算
             if div_yield is None or div_yield > 0.2:
                 div_yield = div_rate / current_price

        # 成長率の取得と補正 (earningsGrowth などが None の場合)
        rev_growth = info.get("revenueGrowth")
        earn_growth = info.get("earningsGrowth")
        peg_ratio = info.get("pegRatio")
        
        try:
            # yfinanceのquarterly_financialsから直接最新の成長率を計算試行
            q_fin = stock.quarterly_financials
            if q_fin is not None and not q_fin.empty:
                q_fin = q_fin.sort_index(axis=1, ascending=False) # 最新が左 (デフォルト)
                cols = q_fin.columns
                
                # 前年同期比 (= 4四半期前と比較)
                if len(cols) >= 5:
                    cur_col = cols[0]
                    prev_year_col = cols[4] # 1年前
                    
                    # Revenue Growth
                    if rev_growth is None:
                        try:
                            rev_cur = q_fin.loc["Total Revenue", cur_col]
                            rev_prev = q_fin.loc["Total Revenue", prev_year_col]
                            if rev_prev and rev_prev != 0:
                                rev_growth = (rev_cur - rev_prev) / rev_prev
                        except: pass
                        
                    # Earnings Growth (Net Income)
                    if earn_growth is None:
                        try:
                            net_cur = q_fin.loc["Net Income", cur_col]
                            net_prev = q_fin.loc["Net Income", prev_year_col]
                            if net_prev and net_prev != 0:
                                earn_growth = (net_cur - net_prev) / abs(net_prev)
                        except: pass
                        
            # FCF Margin Growth Calculation
            fcf_margin_growth = None
            try:
                q_cf = stock.quarterly_cashflow
                q_fin = stock.quarterly_financials
                if q_cf is not None and not q_cf.empty and q_fin is not None and not q_fin.empty:
                    # 日付でソート（最新が右になるように一旦反転させて比較もしやすくするか、yfinanceは最新が左(col[0])）
                    # 最新 = col[0], 1年前 = col[4] (もしあれば) または 前四半期 = col[1]
                    # Growth rate usually implies YoY or QoQ. Let's do YoY for consistency with others, or QoQ if requested previously?
                    # The previous chart code was doing sequential calculation. "Growth Rate" in metrics usually YoY.
                    # User request "FCFマージン成長率". Let's calculate YoY change in FCF Margin.
                    
                    # Align columns
                    common_cols = q_cf.columns.intersection(q_fin.columns)
                    if len(common_cols) >= 5:
                        cur_col = common_cols[0]
                        prev_year_col = common_cols[4]
                        
                        # Current FCF Margin
                        try:
                            ocf_cur = q_cf.loc["Operating Cash Flow", cur_col]
                            capex_cur = q_cf.loc["Capital Expenditure", cur_col]
                            rev_cur = q_fin.loc["Total Revenue", cur_col]
                            if rev_cur and rev_cur != 0:
                                fcf_cur = ocf_cur + capex_cur
                                margin_cur = fcf_cur / rev_cur
                                
                                # Previous Year FCF Margin
                                ocf_prev = q_cf.loc["Operating Cash Flow", prev_year_col]
                                capex_prev = q_cf.loc["Capital Expenditure", prev_year_col]
                                rev_prev = q_fin.loc["Total Revenue", prev_year_col]
                                
                                if rev_prev and rev_prev != 0:
                                    fcf_prev = ocf_prev + capex_prev
                                    margin_prev = fcf_prev / rev_prev
                                    
                                    # Growth of the margin itself (percentage point change or relative growth?)
                                    # Usually "Margin Growth" is ambiguous. Often means did the margin expand?
                                    # Let's take (Margin Current - Margin Prev) / abs(Margin Prev) * 100 for growth rate,
                                    # Or just simple difference if it's small numbers? 
                                    # Previous code was: (Margin_i - Margin_i-1) / abs(Margin_i-1) * 100
                                    # So it is relative growth rate of the percentage value.
                                    if margin_prev != 0:
                                        fcf_margin_growth = (margin_cur - margin_prev) / abs(margin_prev)
                        except: pass
            except Exception as e:
                print(f"FCF Calc Error: {e}")

        except:
            pass
            
        # PEGレシオの算出 (もしなければ)
        # PEG = PER / (Earnings Growth Rate * 100)
        # 使用するPERは通常TrailingかForward。ここではTrailingを使用。
        if peg_ratio is None:
            pe = info.get("trailingPE")
            if pe and earn_growth and earn_growth > 0:
                peg_ratio = pe / (earn_growth * 100)
            elif info.get("forwardPE") and earn_growth and earn_growth > 0:
                 peg_ratio = info.get("forwardPE") / (earn_growth * 100)

        # 辞書に追加・上書き
        basic_info = {
            # 既存のreturn文にあるものをここに移動
            "name": info.get("longName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "country": info.get("country", "N/A"),
            "website": info.get("website", ""),
            "summary": info.get("longBusinessSummary", "情報なし"),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", None),
            "forward_pe": info.get("forwardPE", None),
            "dividend_yield": div_yield, # 補正済み
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", None),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", None),
            "current_price": current_price,
            "target_price": info.get("targetMeanPrice", None),
            
            "grossMargins": info.get("grossMargins"),
            "operatingMargins": info.get("operatingMargins"),
            "profitMargins": info.get("profitMargins"),
            "returnOnEquity": info.get("returnOnEquity"),
            "returnOnAssets": info.get("returnOnAssets"),
            "revenueGrowth": rev_growth, # 補正済み
            "earningsGrowth": earn_growth, # 補正済み
            "fcfMarginGrowth": fcf_margin_growth, # 追加
            "beta": info.get("beta"),
            "currentRatio": info.get("currentRatio"),
            "debtToEquity": info.get("debtToEquity"),
            "fullTimeEmployees": info.get("fullTimeEmployees"),
            "pegRatio": peg_ratio, # 補正済み
            "priceToBook": info.get("priceToBook"),
            "priceToSalesTrailing12Months": info.get("priceToSalesTrailing12Months"),
        }
        return basic_info
    except Exception as e:
        print(f"Error fetching info for {ticker}: {e}")
        return {"name": ticker, "summary": "情報を取得できませんでした", "current_price": 0}


def get_option_chain(ticker: str) -> Optional[tuple[pd.DataFrame, pd.DataFrame]]:
    """
    オプションチェーンデータを取得します。
    
    Args:
        ticker: 銘柄コード (SPY, QQQ, IWM など)
    
    Returns:
        (calls_df, puts_df) のタプル、または取得失敗時はNone
    """
    try:
        stock = yf.Ticker(ticker)
        # 最も直近の満期日を取得
        expirations = stock.options
        if not expirations:
            return None
        
        # 直近2つの満期日のオプションを取得
        all_calls = []
        all_puts = []
        for exp in expirations[:3]:  # 直近3つの満期日
            opt = stock.option_chain(exp)
            calls = opt.calls.copy()
            puts = opt.puts.copy()
            calls["expiration"] = exp
            puts["expiration"] = exp
            all_calls.append(calls)
            all_puts.append(puts)
        
        calls_df = pd.concat(all_calls, ignore_index=True)
        puts_df = pd.concat(all_puts, ignore_index=True)
        
        return calls_df, puts_df
    except Exception as e:
        print(f"Error fetching options for {ticker}: {e}")
        return None


from src.market_config import get_market_config


def _get_stooq_data(ticker: str, period_days: int = 5) -> tuple[float, float] | None:
    """
    Stooq からデータを取得します。
    
    Args:
        ticker: Stooq ティッカー
        period_days: 取得期間（日数）
    
    Returns:
        (現在価格, 変化率%) または None
    """
    try:
        from pandas_datareader import data as pdr
        from datetime import datetime, timedelta
        
        end = datetime.now()
        start = end - timedelta(days=period_days + 5)  # 余裕を持って取得
        
        df = pdr.DataReader(ticker, "stooq", start, end)
        if df.empty or len(df) < 2:
            return None
        
        # Stooq は新しい日付が先頭
        df = df.sort_index()
        current = df["Close"].iloc[-1]
        prev = df["Close"].iloc[-2]
        change = ((current - prev) / prev) * 100
        
        return (current, change)
    except Exception as e:
        print(f"Stooq fetch error for {ticker}: {e}")
        return None


# 日本市場用 Stooq ティッカーマッピング
JP_STOOQ_TICKERS = {
    # 株式指数
    "日経平均": "^NKX",
    "TOPIX": "^TPX",
    "東証グロース250": "^TSM",
    "JPX日経400": "^JNI",
    # 金利
    "日本10年金利": "10YJP.B",
    "日本2年金利": "2YJP.B",
}


@st.cache_data(ttl=300)  # 5分間キャッシュ
def get_market_indices(market_type: str = "US") -> dict[str, dict]:
    """
    主要市場指数のデータを取得します。
    日本市場: Stooq をプライマリソースとして使用
    米国市場: yfinance を使用
    
    Args:
        market_type: "US" または "JP"
    
    Returns:
        指数名をキーとする価格情報の辞書
    """
    config = get_market_config(market_type)
    result = {}
    
    # ========================================
    # 日本市場: Stooq をプライマリソースとして使用
    # ========================================
    if market_type == "JP":
        # 1. Stooq から主要指数・金利を取得
        for name, stooq_ticker in JP_STOOQ_TICKERS.items():
            data = _get_stooq_data(stooq_ticker)
            if data:
                price, change = data
                result[name] = {
                    "price": price,
                    "change": change,
                    "ticker": stooq_ticker
                }
        
        # 2. コモディティ・FX・暗号資産は yfinance から取得（グローバルデータ）
        global_tickers = {
            **config["commodities"],
            **config["crypto"],
            **config["forex"]
        }
        for name, ticker in global_tickers.items():
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="5d")["Close"]
                if len(hist) >= 2:
                    current = hist.iloc[-1]
                    prev = hist.iloc[-2]
                    change = ((current - prev) / prev) * 100
                    result[name] = {"price": current, "change": change, "ticker": ticker}
            except Exception:
                pass
        
        return result
    
    # ========================================
    # 米国市場: yfinance を使用（従来ロジック）
    # ========================================
    indices = config["indices"]
    sectors = config.get("sectors", {})
    treasuries = config["treasuries"]
    commodities = config["commodities"]
    crypto = config["crypto"]
    forex = config["forex"]
    
    all_tickers = {**indices, **sectors, **treasuries, **commodities, **crypto, **forex}
    
    # 一括取得で高速化
    ticker_list = list(all_tickers.values())
    if not ticker_list:
        return {}
        
    try:
        data = yf.download(ticker_list, period="5d", group_by="ticker", progress=False, threads=True)
    except Exception as e:
        print(f"Batch download failed: {e}")
        data = pd.DataFrame()
    
    is_multi_index = isinstance(data.columns, pd.MultiIndex) if not data.empty else False
    
    for name, ticker in all_tickers.items():
        hist = None
        try:
            if not data.empty:
                if is_multi_index and ticker in data.columns.levels[0]:
                    hist = data[ticker]["Close"].dropna()
                elif not is_multi_index and ticker == ticker_list[0]:
                    hist = data["Close"].dropna()
            
            # フォールバック: 個別取得
            if hist is None or len(hist) == 0:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="5d")["Close"]
            
            if len(hist) >= 2:
                current = hist.iloc[-1]
                prev = hist.iloc[-2]
                change = ((current - prev) / prev) * 100
                result[name] = {"price": current, "change": change, "ticker": ticker}
            elif len(hist) == 1:
                result[name] = {"price": hist.iloc[-1], "change": 0, "ticker": ticker}
        except Exception:
            pass
    
    return result


def get_stock_news(ticker: str, max_items: int = 10) -> list[dict]:
    """
    銘柄に関連するニュースを取得します。
    
    Args:
        ticker: 銘柄コード
        max_items: 取得する最大ニュース数
    
    Returns:
        ニュース記事のリスト
    """
    try:
        stock = yf.Ticker(ticker)
        news_data = stock.news[:max_items] if stock.news else []
        
        results = []
        for item in news_data:
            # 新しいyfinance形式に対応（contentが入れ子になっている場合）
            if "content" in item:
                content = item["content"]
                title = content.get("title", "")
                provider = content.get("provider", {})
                publisher = provider.get("displayName", "") if isinstance(provider, dict) else ""
                
                # リンクの取得
                canonical_url = content.get("canonicalUrl", {})
                link = canonical_url.get("url", "") if isinstance(canonical_url, dict) else ""
                
                # 日付の取得
                pub_date = content.get("pubDate", "")
                if pub_date:
                    published = pub_date[:16].replace("T", " ")
                else:
                    published = "日時不明"

                # 概要の取得
                summary = content.get("summary", "")
            else:
                # 旧形式
                title = item.get("title", "")
                publisher = item.get("publisher", "")
                link = item.get("link", "")
                summary = "" # 旧形式では概要取得困難な場合が多い
                pub_time = item.get("providerPublishTime", 0)
                if pub_time and pub_time > 0:
                    published = datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M")
                else:
                    published = "日時不明"
            
            if title:  # タイトルがある場合のみ追加
                results.append({
                    "title": title,
                    "publisher": publisher,
                    "link": link,
                    "published": published,
                    "summary": summary
                })
        
        return results
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return []
