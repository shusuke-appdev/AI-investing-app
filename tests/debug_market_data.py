
import sys
import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.market_data import get_market_indices
from src.theme_analyst import fetch_and_calculate_all_performances
from src.market_config import US_CONFIG

def test_sectors():
    print("\n--- Testing Sector Indices (US) ---")
    sectors = US_CONFIG["sectors"]
    print(f"Target Sectors: {list(sectors.keys())}")
    
    # Try fetching directly via yfinance to see if they exist/have data
    tickers = list(sectors.values())
    print(f"Fetching tickers: {tickers}")
    
    data = yf.download(tickers, period="2d", group_by='ticker', threads=True)
    
    for name, ticker in sectors.items():
        try:
            if len(tickers) > 1:
                df = data[ticker]
            else:
                df = data
            
            if df.empty:
                print(f"[FAIL] {name} ({ticker}): Empty DataFrame")
                continue
                
            last_price = df["Close"].iloc[-1]
            print(f"[OK] {name} ({ticker}): {last_price}")
        except Exception as e:
            print(f"[ERROR] {name} ({ticker}): {e}")

def test_themes():
    print("\n--- Testing Theme Performance ---")
    
    # Test 5 days
    print("Fetching 5 days performance...")
    perf_5d = fetch_and_calculate_all_performances(5, "US")
    print(f"5d Sample (NVDA): {perf_5d.get('NVDA')}")
    
    # Test 1 month
    print("Fetching 30 days performance...")
    perf_1mo = fetch_and_calculate_all_performances(30, "US")
    print(f"1mo Sample (NVDA): {perf_1mo.get('NVDA')}")
    
    if perf_5d.get('NVDA') == perf_1mo.get('NVDA'):
        print("[WARNING] 5d and 1mo performance are IDENTICAL!")
    else:
        print("[OK] 5d and 1mo performance are different.")

if __name__ == "__main__":
    test_sectors()
    test_themes()
