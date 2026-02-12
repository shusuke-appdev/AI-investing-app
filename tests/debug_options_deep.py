
import sys
import os
import yfinance as yf
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.market_data import get_option_chain

def debug_options():
    ticker = "SPY"
    print(f"--- Debugging Options for {ticker} ---")
    
    # 1. Direct yfinance call
    print("\n[1] Calling yf.Ticker(ticker).options...")
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        print(f"Expirations found: {len(exps)}")
        if exps:
            print(f"First 3 exp: {exps[:3]}")
    except Exception as e:
        print(f"Direct yfinance error: {e}")
        
    # 2. via get_option_chain
    print("\n[2] Calling src.market_data.get_option_chain(ticker)...")
    res = get_option_chain(ticker)
    if res:
        calls, puts = res
        print(f"Result: {len(calls)} calls, {len(puts)} puts")
    else:
        print("Result: None")

if __name__ == "__main__":
    debug_options()
