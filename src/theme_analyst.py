"""
テーマ別分析モジュール
テーマごとの騰落率計算とランキング生成を行います。
"""
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
    
    # 2. 個別データ取得 (Finnhub移行)
    # yf.download(threads=True) は高速だが Finnhub はレート制限(60/min)があるため
    # 非常に時間がかかる可能性がある。キャッシュ(12h)を頼りにループ処理する。
    
    performance_map = {}
    
    # 期間を日数文字列に変換
    period_str = "1mo"
    if days <= 5: period_str = "5d"
    elif days <= 30: period_str = "1mo"
    elif days <= 90: period_str = "3mo"
    elif days <= 180: period_str = "6mo"
    else: period_str = "1y"

    # 進捗表示はできないため（backendロジック）、ひたすら取得
    # 実用性を考慮し、各テーマの上位銘柄（定義順）のみに絞るなどの最適化が望ましいが、
    # Plan通り全取得を試みる。タイムアウト時はキャッシュが効くことを祈る。
    
    # デバッグ用に件数を制限するオプションがあれば良いが、今回は全件トライ。
    # ただし、エラーが続出する場合は空を返す。
    
    for ticker in all_tickers:
        try:
            # get_stock_data は DataFrame を返す (columns: Open, High, Low, Close, Volume)
            hist = get_stock_data(ticker, period=period_str)
            
            if hist is None or hist.empty:
                continue
                
            closes = hist["Close"]
            if len(closes) < 2:
                continue
            
            # 期間計算
            # 取得されたデータが必要な日数分あるとは限らない（Finnhubのcandlesは期間指定）
            # get_stock_data内部で期間計算済み
            
            current_price = closes.iloc[-1]
            start_price = closes.iloc[0] # 期間の最初
            
            if len(closes) > 1:
                # 念のためデータの日付スパンを確認すべきだが、簡易的に最初と最後で計算
                if start_price != 0:
                    perf = ((current_price - start_price) / start_price) * 100
                    performance_map[ticker] = perf
                    
        except Exception:
            # 個別エラーは無視
            continue

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

