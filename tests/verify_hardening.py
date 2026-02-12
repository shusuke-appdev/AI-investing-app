
import sys
import os
import streamlit as st
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.market_data import get_market_indices, get_option_chain
from src.finnhub_client import get_quote

def test_hardening():
    print(f"--- Hardening Verification Start around {datetime.now()} ---")
    
    # 1. Test Market Indices (should show INFO/ERROR logs if Finnhub fails)
    print("\n[Test 1] Fetching Market Indices (US)...")
    indices = get_market_indices("US")
    print(f"Indices keys: {list(indices.keys())}")
    
    # 2. Test Market Indices (JP) - checks Stooq and sectors
    print("\n[Test 2] Fetching Market Indices (JP)...")
    indices_jp = get_market_indices("JP")
    print(f"JP Indices keys: {list(indices_jp.keys())}")

    # 3. Test Option Chain for SPY (Expect WARN/ERROR logs or successful Volume fallback inside app logic, but here just fetch)
    print("\n[Test 3] Fetching SPY Options...")
    options = get_option_chain("SPY")
    if options:
        calls, puts = options
        print(f"SPY Options fetched: {len(calls)} calls, {len(puts)} puts")
    else:
        print("SPY Options: None (Check logs for [DATA_WARN] or [DATA_ERROR])")

    # 4. Test Bogus Ticker for Finnhub to see error log
    print("\n[Test 4] Fetching Bogus Ticker 'INVALID_TICKER_XYZ'...")
    q = get_quote("INVALID_TICKER_XYZ")
    print(f"Quote result: {q}")

if __name__ == "__main__":
    test_hardening()
