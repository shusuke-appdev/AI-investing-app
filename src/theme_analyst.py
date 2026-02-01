"""
テーマ別分析モジュール
テーマごとの騰落率計算とランキング生成を行います。
"""
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional
import sys
import os

# 親ディレクトリのインポート用
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from themes_config import THEMES, PERIODS



def fetch_and_calculate_all_performances(days: int) -> dict[str, float]:
    """
    全テーマの構成銘柄を一括取得して騰落率を計算します。
    
    Returns:
        {ticker: performance} の辞書
    """
    # 1. 全銘柄リストの作成
    all_tickers = set()
    for tickers in THEMES.values():
        all_tickers.update(tickers)
    
    all_tickers = list(all_tickers)
    if not all_tickers:
        return {}
    
    # 2. 一括データ取得 (yf.download)
    # 期間は指定日数 + 余裕 (土日祝考慮して1.5倍〜2倍程度、あるいはシンプルに '6mo' など)
    # days=1 -> 5d, days=5 -> 1mo, days=30 -> 3mo, days=90 -> 6mo
    period = "1mo"
    if days > 5: period = "3mo"
    if days > 30: period = "6mo"
    
    try:
        # group_by='ticker' でマルチインデックス取得
        data = yf.download(all_tickers, period=period, group_by='ticker', threads=True, progress=False)
    except Exception as e:
        print(f"Batch Download Error: {e}")
        return {}

    performance_map = {}
    
    # 3. 各銘柄のパフォーマンス計算
    # dataのカラム構造: (Ticker, PriceType) または Ticker (単一銘柄の場合)
    # yfinanceの仕様変更で、Tickerが1つの場合はマルチインデックスにならない場合があるが、
    # listで渡していれば基本マルチになるはず。ただし全滅時などは空。
    
    if data.empty:
        return {}

    # 単一銘柄の場合の対応 (columnsがMultiIndexでない場合)
    is_multi_index = isinstance(data.columns, pd.MultiIndex)
    
    for ticker in all_tickers:
        try:
            if is_multi_index:
                # 該当Tickerのデータがあるか確認
                if ticker not in data.columns.levels[0]:
                    continue  # データなし
                hist = data[ticker] # DataFrame with Open, High, Low, Close...
            else:
                # 単一銘柄で渡した、あるいはデータ構造が違う場合。
                # ここではall_tickersが複数ある前提なのでMultiIndex処理が主。
                # 万が一のためのfallback (Tickerが1個だけリストにある場合など)
                if ticker == all_tickers[0]:
                    hist = data
                else:
                    continue

            # Closeデータの抽出とクリーニング
            if "Close" not in hist.columns:
                continue
                
            closes = hist["Close"].dropna()
            
            if len(closes) < 2:
                continue
                
            # 指定日数前の価格を取得
            # closesは日付インデックス(昇順)
            if len(closes) <= days:
                start_price = closes.iloc[0]
            else:
                start_price = closes.iloc[-days-1]
            
            end_price = closes.iloc[-1]
            
            if start_price == 0 or pd.isna(start_price) or pd.isna(end_price):
                continue
                
            perf = ((end_price - start_price) / start_price) * 100
            performance_map[ticker] = perf
            
        except Exception as e:
            # 個別計算エラーはスキップ
            continue
            
    return performance_map


import streamlit as st

@st.cache_data(ttl=43200)  # 12時間キャッシュ
def get_ranked_themes(period_name: str) -> list[dict]:
    """
    指定期間での全テーマをパフォーマンス順（降順）で取得します。
    
    Args:
        period_name: 期間名 ("1日", "5日", etc.)
    
    Returns:
        全テーマのリスト（パフォーマンス順）
    """
    if period_name not in PERIODS:
        raise ValueError(f"Unknown period: {period_name}")
    
    days = PERIODS[period_name]
    ticker_performances = fetch_and_calculate_all_performances(days)
    
    theme_performances = []
    
    for theme_name, tickers in THEMES.items():
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

