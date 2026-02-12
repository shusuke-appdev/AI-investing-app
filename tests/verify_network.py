
import sys
import os
import streamlit as st
import pandas as pd
import time

# Mock st.cache_data to allow execution without streamlit run
if not hasattr(st, "cache_data"):
    def cache_dummy(ttl=None):
        def decorator(func):
            return func
        return decorator
    st.cache_data = cache_dummy
    
if not hasattr(st, "cache_resource"):
    def cache_dummy(ttl=None):
        def decorator(func):
            return func
        return decorator
    st.cache_resource = cache_dummy

# Add src to path
sys.path.insert(0, os.getcwd())

from src.network import get_session
from src.market_data import get_stock_data

def test_network_session():
    print("--- Testing src.network.get_session ---")
    session = get_session()
    print(f"Session object: {session}")
    print(f"Headers: {session.headers}")
    
    # Check User-Agent
    ua = session.headers.get("User-Agent")
    if "Mozilla" in ua:
        print("[PASS] User-Agent is set correctly.")
    else:
        print(f"[FAIL] User-Agent is missing or incorrect: {ua}")
        
    # Check Cache (if available)
    if hasattr(session, "cache"):
        print("[INFO] requests-cache is ENABLED.")
    else:
        print("[INFO] requests-cache is DISABLED (standard requests.Session).")

def test_market_data_fetch():
    print("\n--- Testing src.market_data.get_stock_data (fallback to yfinance) ---")
    # Using a ticker that likely falls back to yfinance if finnhub is not configured or for testing
    # Force yfinance fallback by disabling finnhub config check mock if necessary, 
    # but currently get_stock_data tries Finnhub first.
    # We can try a ticker that Finnhub might miss or just standard AAPL.
    
    ticker = "AAPL"
    try:
        df = get_stock_data(ticker, period="5d")
        if not df.empty:
            print(f"[PASS] Fetched {len(df)} rows for {ticker}")
            print(df.tail(2))
        else:
            print(f"[WARN] Fetched empty data for {ticker}")
    except Exception as e:
        print(f"[FAIL] Error fetching data: {e}")

if __name__ == "__main__":
    test_network_session()
    test_market_data_fetch()
