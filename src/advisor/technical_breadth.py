import logging
from io import StringIO

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)

@st.cache_data(ttl=24*3600)
def get_sp500_components() -> list[str]:
    """S&P 500の構成銘柄リストを取得する。"""
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0'}
        html = requests.get(url, headers=headers).text
        tables = pd.read_html(StringIO(html))
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].str.replace('.', '-', regex=False).tolist()
        return tickers
    except Exception as e:
        logger.error(f"S&P 500銘柄のパースに失敗しました: {e}")
        return []

@st.cache_data(ttl=3600*4)
def fetch_breadth_data(period: str = "6mo") -> pd.DataFrame:
    """
    S&P 500構成銘柄の日次データを取得し、毎日の値上がり銘柄数・値下がり銘柄数を集計する。
    Returns:
        pd.DataFrame (index: Date, columns: ['Advances', 'Declines', 'Net_Advances', 'Total_Issues'])
    """
    tickers = get_sp500_components()
    if not tickers:
        return pd.DataFrame()

    try:
        data = yf.download(tickers, period=period, progress=False)['Close']
        if data.empty:
            return pd.DataFrame()

        diff = data.diff()

        advances = (diff > 0).sum(axis=1)
        declines = (diff < 0).sum(axis=1)
        total_issues = data.notna().sum(axis=1)

        net_advances = advances - declines

        df = pd.DataFrame({
            'Advances': advances,
            'Declines': declines,
            'Net_Advances': net_advances,
            'Total_Issues': total_issues
        }).dropna()

        # 不要な最初の行(差分がないため)を除外
        if (df['Advances'] == 0).all() and (df['Declines'] == 0).all():
           df = df.iloc[1:]

        return df
    except Exception as e:
        logger.error(f"騰落データの取得に失敗しました: {e}")
        return pd.DataFrame()

def calculate_sp_oscillator(breadth_df: pd.DataFrame) -> dict:
    """
    S&Pオシレーターを計算する。
    10日間のSMA（Net Advancesの平均）、および全体に対するパーセンテージ。
    """
    if breadth_df is None or breadth_df.empty or len(breadth_df) < 10:
        return {"oscillator_value": 0.0, "oscillator_percent": 0.0, "signal": "中立"}

    sma_10 = breadth_df['Net_Advances'].rolling(10).mean()
    avg_total = breadth_df['Total_Issues'].rolling(10).mean()

    current_osc = float(sma_10.iloc[-1])
    current_avg_total = float(avg_total.iloc[-1])

    percent = (current_osc / current_avg_total * 100) if current_avg_total > 0 else 0.0

    if percent >= 5.0:
        signal = "買われすぎ (Overbought)"
    elif percent <= -5.0:
        signal = "売られすぎ (Oversold)"
    else:
        signal = "中立"

    return {
        "oscillator_value": round(current_osc, 2),
        "oscillator_percent": round(percent, 2),
        "signal": signal
    }

def calculate_mcclellan_oscillator(breadth_df: pd.DataFrame) -> dict:
    """
    McClellan Oscillatorを計算する。
    19日EMA(Net Advances) - 39日EMA(Net Advances)
    """
    if breadth_df is None or breadth_df.empty or len(breadth_df) < 39:
        return {"mcclellan_value": 0.0, "signal": "中立"}

    net_advances = breadth_df['Net_Advances']
    ema_19 = net_advances.ewm(span=19, adjust=False).mean()
    ema_39 = net_advances.ewm(span=39, adjust=False).mean()

    mcclellan = ema_19 - ema_39

    # 0クロスによるシグナル、または極端な値による買われすぎ・売られすぎ
    # 一般的にMcClellanが+100以上で買われすぎ、-100以下で売られすぎとする
    current_val = float(mcclellan.iloc[-1])

    if current_val >= 100:
        signal = "買われすぎ"
    elif current_val <= -100:
        signal = "売られすぎ"
    elif current_val > 0:
        signal = "強気"
    else:
        signal = "弱気"

    return {
        "mcclellan_value": round(current_val, 2),
        "signal": signal
    }
