import sys
import os
import yfinance as yf

# srcディレクトリをパスに追加
sys.path.append(os.path.abspath('.'))

from src.advisor.minervini_analyzer import detect_vcp, analyze_stage, detect_follow_through_day
from src.market_data import get_stock_data

def test_vcp():
    print("--- テスト: VCP & Stage Analysis ---")
    ticker = "NVDA"
    print(f"銘柄: {ticker}")
    df = get_stock_data(ticker, "2y")
    
    if df is not None and not df.empty:
        # VCP
        is_vcp, vcp_info = detect_vcp(df)
        print(f"VCP 検知: {is_vcp}")
        if is_vcp:
            print(f"  詳細: {vcp_info}")
            
        # Stage
        stage_info = analyze_stage(df)
        print(f"Stage 判定: {stage_info}")
    else:
        print("データ取得失敗")

def test_ftd():
    print("\n--- テスト: Follow Through Day ---")
    ticker = "SPY"
    print(f"銘柄: {ticker}")
    df = get_stock_data(ticker, "6mo")
    
    if df is not None and not df.empty:
        ftd_info = detect_follow_through_day(df)
        print(f"FTD 判定: {ftd_info}")
    else:
        print("データ取得失敗")

if __name__ == "__main__":
    test_vcp()
    test_ftd()
