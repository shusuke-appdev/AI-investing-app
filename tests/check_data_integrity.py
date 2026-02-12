
import sys
import os
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.finnhub_client import get_company_news
from src.news_aggregator import get_aggregated_news

def test_data_integrity():
    print(f"Current System Time: {datetime.now()}")
    
    # 1. News Freshness
    print("\n--- 1. Testing News Freshness ---")
    
    # Finnhub
    print("Checking Finnhub News (AAPL)...")
    try:
        f_news = get_company_news("AAPL")
        if f_news:
            latest = datetime.fromtimestamp(f_news[0]['datetime'])
            print(f"   Latest Finnhub item: {latest} (Title: {f_news[0]['headline'][:30]}...)")
            # Check if within 24h
            if (datetime.now() - latest).days > 1:
                print("   [WARNING] Finnhub news looks OLD.")
        else:
            print("   [WARNING] No Finnhub news found.")
    except Exception as e:
        print(f"   [ERROR] Finnhub news error: {e}")

    # GNews (via aggregator)
    print("Checking GNews Aggregator...")
    try:
        g_news = get_aggregated_news(categories=["BUSINESS"], max_per_source=3)
        if g_news:
            # aggregator returns 'published' string, need to parse or check raw
            print(f"   Sample GNews item: {g_news[0]}")
        else:
            print("   [WARNING] No GNews items found.")
    except Exception as e:
        print(f"   [ERROR] GNews error: {e}")


    # 2. Option Data Quality
    print("\n--- 2. Testing Option Data Quality (OI Check) ---")
    tickers = ["SPY", "QQQ", "IWM", "NVDA"]
    
    for ticker in tickers:
        print(f"Checking {ticker}...")
        try:
            t = yf.Ticker(ticker)
            exps = t.options
            if not exps:
                print(f"   [FAIL] No expirations for {ticker}")
                continue
                
            # Check first expiration
            chain = t.option_chain(exps[0])
            calls = chain.calls
            
            # Check OI
            oi_sum = calls['openInterest'].sum()
            vol_sum = calls['volume'].sum()
            
            print(f"   Exp: {exps[0]} | Calls OI Sum: {oi_sum} | Volume Sum: {vol_sum}")
            
            if oi_sum == 0:
                print("   [CRITICAL] Open Interest is ZERO. Data is likely delayed or insufficient.")
            else:
                print("   [OK] Open Interest seems populated.")
                
        except Exception as e:
            print(f"   [ERROR] {e}")

if __name__ == "__main__":
    test_data_integrity()
