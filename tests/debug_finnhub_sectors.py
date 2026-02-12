
import sys
import os
import streamlit as st

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.finnhub_client import get_quote, get_candles

# Mock session state for API key if needed (assuming env var is set or user has it)
# The finnhub_client checks st.session_state then os.environ.
# We will check if we can get a client.

def test_finnhub_sectors():
    print("Testing Finnhub Sector Data...")
    
    ticker = "XLK" # Technology Select Sector SPDR Fund
    
    try:
        print(f"Fetching Quote for {ticker}...")
        quote = get_quote(ticker)
        print(f"Quote Result: {quote}")
        
        if quote and quote.get('c', 0) > 0:
            print("[SUCCESS] Quote fetched successfully.")
        else:
            print("[FAIL] Quote is empty or invalid.")
            
            # Try candles as fallback
            print(f"Fetching Candles for {ticker} (Last 5 days)...")
            candles = get_candles(ticker, period_days=5)
            if not candles.empty:
                print(f"Candles Result:\n{candles.tail()}")
                print("[SUCCESS] Candles fetched successfully.")
            else:
                print("[FAIL] Candles also failed.")

    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")

if __name__ == "__main__":
    test_finnhub_sectors()
