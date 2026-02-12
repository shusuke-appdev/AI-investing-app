"""
テーマ別分析モジュール
テーマごとの騰落率計算とランキング生成を行います。
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import sys
import os

# 親ディレクトリのインポート用
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from themes_config import THEMES, PERIODS, get_themes
from src.market_data import get_stock_data



def fetch_and_calculate_all_performances(days: int, market_type: str = "US") -> dict[str, float]:
    """
    全テーマの構成銘柄を一括取得して騰落率を計算します。
    
    Args:
        days: 期間（日数）
        market_type: "US" または "JP"
    
    Returns:
        {ticker: performance} の辞書
    """
    themes = get_themes(market_type)
    
    # 1. 全銘柄リストの作成
    all_tickers = set()
    for tickers in themes.values():
        all_tickers.update(tickers)
    
    all_tickers = list(all_tickers)
    if not all_tickers:
        return {}
    
    # 2. 一括取得 (yfinance batch)
    # 期間に応じた適切なデータを取得し、日付ベースで計算する
    
    # 期間設定を長めに確保して、確実に過去データが含まれるようにする
    fetch_period = "1mo"
    interval = "1d"
    
    if days <= 5: 
        fetch_period = "1mo" # 5日でも1ヶ月分取っておけば確実
        interval = "1d" 
    elif days <= 30: 
        fetch_period = "3mo"
    elif days <= 90: 
        fetch_period = "6mo"
    elif days <= 180: 
        fetch_period = "1y"
    else: 
        fetch_period = "2y" # 1年以上なら2年分
    
    performance_map = {}
    
    try:
        # yfinanceで一括ダウンロード
        df = yf.download(all_tickers, period=fetch_period, interval=interval, group_by='ticker', auto_adjust=True, threads=True, progress=False)
        
        if df.empty:
            return {}
            
        # 1銘柄だけの場合のハンドリング
        if len(all_tickers) == 1:
            pass # 通常はMultiIndexではないが、アクセス方法を統一する必要がある

        for ticker in all_tickers:
            try:
                # データ抽出
                if len(all_tickers) > 1:
                    if ticker not in df.columns.levels[0]:
                        continue
                    stock_df = df[ticker]
                else:
                    stock_df = df
                
                if "Close" not in stock_df.columns:
                    continue
                    
                closes = stock_df["Close"].dropna()
                if len(closes) < 2:
                    continue
                
                # 最新日付と価格
                current_date = closes.index[-1]
                current_price = closes.iloc[-1]
                
                # 目標とする開始日 (営業日ベースで厳密に計算)
                target_date = current_date - timedelta(days=days)
                
                # target_date 以前で最も近い日付を探す (asof)
                # get_indexer は method='nearest' が使えるが、未来方向に行くと期間が短くなるので
                # target_date "以下" の最大日付を探したい。
                # 簡易的に、indexから target_date 以下のものをフィルタして最後を取得
                
                past_data = closes[closes.index <= target_date]
                if past_data.empty:
                    # データ不足（上場から日が浅いなど）の場合は、ある最古データを使うか、計算しないか。
                    # ここでは最古データを使う（期間が短くなるがエラーにはしない）
                    start_price = closes.iloc[0]
                else:
                    start_price = past_data.iloc[-1]
                
                if start_price != 0:
                    perf = ((current_price - start_price) / start_price) * 100
                    performance_map[ticker] = perf
                    
            except Exception as e:
                # print(f"Error for {ticker}: {e}")
                continue
                
    except Exception as e:
        print(f"Batch download error: {e}")
        return {}

    return performance_map


import streamlit as st

@st.cache_data(ttl=43200)  # 12時間キャッシュ
def get_ranked_themes(period_name: str, market_type: str = "US") -> list[dict]:
    """
    指定期間での全テーマをパフォーマンス順（降順）で取得します。
    
    Args:
        period_name: 期間名 ("1日", "5日", etc.)
        market_type: "US" または "JP"
    
    Returns:
        全テーマのリスト（パフォーマンス順）
    """
    if period_name not in PERIODS:
        raise ValueError(f"Unknown period: {period_name}")
    
    days = PERIODS[period_name]
    ticker_performances = fetch_and_calculate_all_performances(days, market_type)
    
    themes = get_themes(market_type)
    theme_performances = []
    
    for theme_name, tickers in themes.items():
        stock_perfs = []
        for t in tickers:
            if t in ticker_performances:
                stock_perfs.append({
                    "ticker": t,
                    "performance": ticker_performances[t]
                })
        
        if stock_perfs:
            avg_perf = sum(s["performance"] for s in stock_perfs) / len(stock_perfs)
            stock_perfs.sort(key=lambda x: x["performance"], reverse=True)
            
            theme_performances.append({
                "theme": theme_name,
                "performance": avg_perf,
                "stocks": stock_perfs
            })
    
    # パフォーマンス順にソート (降順)
    theme_performances.sort(key=lambda x: x["performance"], reverse=True)
    
    return theme_performances


def get_top_themes(period_name: str, top_n: int = 10) -> list[dict]:
    """
    指定期間での上位テーマを取得します（互換性維持）。
    """
    ranked = get_ranked_themes(period_name)
    return ranked[:top_n]


def get_theme_details(theme_name: str, period_name: str = "1ヶ月") -> dict:
    """
    テーマの詳細情報を取得します。
    """
    # 既存互換のため残すが、内部でget_top_themes的なロジックを使うか、
    # 単独ダウンロードする。単独の場合は従来のロジックで良いが、
    # 整合性を取るため再実装してもよい。ここでは簡易的に。
    # 「詳細」機能は現状UIであまり使われていない（Expander内はget_top_themesで返されたデータを使っている）。
    return {} # 必要なら実装


def get_all_theme_names() -> list[str]:
    """
    定義されている全テーマ名を取得します。
    
    Returns:
        テーマ名のリスト
    """
    return list(THEMES.keys())

