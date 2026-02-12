import sys
import os
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.getcwd())

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from src.finnhub_client import get_candles

def main():
    ticker = "AAPL"
    resolution = "D"
    now = datetime.now()
    start = now - timedelta(days=30)
    
    print(f"Testing get_candles for {ticker} (Res: {resolution}, Start: {start}, End: {now})...")
    
    try:
        df = get_candles(ticker, resolution, start, now)
        print(f"Result type: {type(df)}")
        if df is not None:
            print(f"Empty: {df.empty}")
            if not df.empty:
                print(df.head())
            else:
                print("DataFrame is empty.")
        else:
            print("Result is None")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()
