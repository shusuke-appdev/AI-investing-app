import sys
import os
import pandas as pd
import streamlit as st
from datetime import datetime

# Setup path and mock Streamlit cache
sys.path.insert(0, os.getcwd())

if not hasattr(st, "cache_data"):
    def cache_dummy(ttl=None):
        def decorator(func):
            return func
        return decorator
    st.cache_data = cache_dummy
    
if not hasattr(st, "cache_resource"):
    st.cache_resource = st.cache_data

# Load imports AFTER setup
from src.market_data import (
    get_stock_data,
    get_stock_info,
    get_market_indices,
    get_stock_news,
    get_option_chain
)
from src.market_config import get_market_config

def log_pass(msg):
    print(f"[PASS] {msg}")

def log_fail(msg):
    print(f"[FAIL] {msg}")

def test_stock_info():
    print("\n--- Testing get_stock_info (AAPL) ---")
    try:
        info = get_stock_info("AAPL")
        if info["name"] != "AAPL" and info["summary"] != "情報なし":
            log_pass(f"Fetched info for {info['name']} ({info['ticker']})")
        else:
            log_fail(f"Info likely incomplete: {info}")
    except Exception as e:
        log_fail(f"Exception: {e}")

def test_market_indices_us():
    print("\n--- Testing get_market_indices ('US') ---")
    try:
        indices = get_market_indices("US")
        if not indices:
            log_fail("Returned empty dict")
            return
            
        required_keys = ["S&P 500 (ETF)", "WTI Oil (ETF)", "Bitcoin", "USD/JPY", "US 10Y Yield", "情報技術"]
        
        for k in required_keys:
            if k in indices:
                data = indices[k]
                log_pass(f"{k} ({data['ticker']}): {data['price']} (Change: {data['change']}%)")
            else:
                log_fail(f"Missing key: {k}")
                
        # Check if sectors loaded (yfinance batch)
        sector_keys = [k for k in indices.keys() if k in ["情報技術", "ヘルスケア"]]
        if sector_keys:
            log_pass(f"Sectors loaded: {len(sector_keys)}")
        else:
             # Sectors are optional/might fail if YF batch fails, but warn.
             print("[WARN] No sectors found (yfinance batch might have failed)")

    except Exception as e:
        log_fail(f"Exception: {e}")

def test_stock_data():
    print("\n--- Testing get_stock_data (AAPL) ---")
    try:
        df = get_stock_data("AAPL", period="5d")
        if not df.empty:
            log_pass(f"Fetched {len(df)} rows")
        else:
            log_fail("Fetched empty DataFrame")
    except Exception as e:
        log_fail(f"Exception: {e}")

def main():
    # Load .env locally if needed
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except:
        pass

    test_stock_info()
    test_stock_data()
    test_market_indices_us()

if __name__ == "__main__":
    main()
