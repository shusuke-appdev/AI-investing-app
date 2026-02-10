import os
import sys
import pandas as pd
from datetime import datetime, timedelta

# プロジェクトルートにパスを通す
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.finnhub_client import (
    is_configured, 
    get_quote, 
    get_candles, 
    get_company_profile, 
    get_basic_financials,
    get_company_news,
    get_earnings_calendar,
    get_earnings_surprises
)
from src.settings_storage import get_finnhub_api_key

def test_finnhub_client():
    print("=== Finnhub Client Test ===")
    
    # API Key Check
    api_key = get_finnhub_api_key()
    print(f"API Key configured in settings: {'Yes' if api_key else 'No'}")
    
    # Set env var for testing if not set via streamlit session
    if api_key:
        os.environ["FINNHUB_API_KEY"] = api_key
    
    if not is_configured():
        print("Skipping tests: Finnhub API Key not configured.")
        return

    symbol = "AAPL"
    print(f"\nTesting with symbol: {symbol}")

    # 1. Quote
    print("\n--- Quote ---")
    quote = get_quote(symbol)
    print(quote)
    if quote and quote['c'] != 0:
        print("✅ Quote OK")
    else:
        print("❌ Quote Failed")

    # 2. Candles
    print("\n--- Candles (1 week) ---")
    candles = get_candles(symbol, period_days=7)
    print(candles.head())
    if not candles.empty:
        print("✅ Candles OK")
    else:
        print("❌ Candles Failed")

    # 3. Profile
    print("\n--- Profile ---")
    profile = get_company_profile(symbol)
    print(profile)
    if profile and profile.get('name'):
        print("✅ Profile OK")
    else:
        print("❌ Profile Failed")
        
    # 4. News
    print("\n--- News ---")
    news = get_company_news(symbol)
    print(f"Items found: {len(news)}")
    if news:
        print(f"Sample: {news[0].get('headline')}")
        print("✅ News OK")
    else:
        print("❌ News Failed (or empty)")

    # 5. Earnings Calendar
    print("\n--- Earnings Calendar (Recent) ---")
    calendar = get_earnings_calendar() # default recent 7 days
    print(f"Calendar events found: {len(calendar)}")
    if calendar:
        print(f"Sample: {calendar[0]}")
        print("✅ Calendar OK")
    else:
        print("⚠️ Calendar Empty (might be normal if no earnings)")

    # 6. Earnings Surprises
    print("\n--- Earnings Surprises ---")
    surprises = get_earnings_surprises(symbol)
    print(surprises)
    if surprises:
        print("✅ Surprises OK")
    else:
        print("❌ Surprises Failed")

if __name__ == "__main__":
    test_finnhub_client()
