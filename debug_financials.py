import sys
import os
import streamlit as st
sys.path.append(os.getcwd())

from src.settings_storage import load_settings, get_finnhub_api_key
load_settings() # Load settings to ensure API key is available
st.session_state = {"finnhub_api_key": get_finnhub_api_key()}

from src.finnhub_client import get_basic_financials, get_financials_reported, get_company_profile
from src.market_data import get_stock_info

ticker = "AAPL"
print(f"--- Testing Data Fetch for {ticker} ---")

# 1. Basic Financials
print("\n[1] Finnhub: Basic Financials")
try:
    basics = get_basic_financials(ticker)
    if basics and "metric" in basics:
        print(f"SUCCESS: Found {len(basics['metric'])} metrics.")
        print(f"Sample: {list(basics['metric'].keys())[:5]}")
    else:
        print(f"FAILED: Empty response or no metric key. Raw: {basics}")
except Exception as e:
    print(f"ERROR: {e}")

# 2. Financials Reported (10-K/Q)
print("\n[2] Finnhub: Financials Reported")
try:
    reported = get_financials_reported(ticker, freq="quarterly")
    if reported:
        print(f"SUCCESS: Found {len(reported)} reports.")
    else:
        print("FAILED: No reports found. (Likely Free Tier limitation)")
except Exception as e:
    print(f"ERROR: {e}")

# 3. YFinance Fallback Check (via script directly)
print("\n[3] YFinance Direct Check")
import yfinance as yf
try:
    y = yf.Ticker(ticker)
    info = y.info
    print(f"YF Info Keys: {len(info)}")
    print(f"YF Sector: {info.get('sector')}")
    print(f"YF MarketCap: {info.get('marketCap')}")
    
    fin = y.quarterly_financials
    if not fin.empty:
        print(f"YF Quarterly Financials: Found {len(fin.columns)} periods.")
    else:
        print("YF Quarterly Financials: Empty")
except Exception as e:
    print(f"YF ERROR: {e}")
