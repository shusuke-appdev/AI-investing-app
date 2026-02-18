import os
import sys

import yfinance as yf

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.market_data import get_option_chain
from src.option_analyst import get_major_indices_options


def test_options():
    print("\n--- Testing Option Data Fetching ---")

    # Test 1: Direct yfinance call for SPY
    ticker = "SPY"
    print(f"1. Testing yf.Ticker('{ticker}').options...")
    try:
        t = yf.Ticker(ticker)
        opts = t.options
        print(f"   Options expirations found: {len(opts)}")
        if opts:
            print(f"   First expiration: {opts[0]}")
            chain = t.option_chain(opts[0])
            print(f"   Calls: {len(chain.calls)}, Puts: {len(chain.puts)}")
        else:
            print("   [WARNING] No expirations found.")
    except Exception as e:
        print(f"   [ERROR] yfinance error: {e}")

    # Test 2: src.market_data.get_option_chain
    print(f"\n2. Testing src.market_data.get_option_chain('{ticker}')...")
    res = get_option_chain(ticker)
    if res:
        calls, puts = res
        print(f"   Success. Calls: {len(calls)}, Puts: {len(puts)}")
    else:
        print("   [FAIL] get_option_chain returned None.")

    # Test 3: src.option_analyst.get_major_indices_options
    print("\n3. Testing src.option_analyst.get_major_indices_options('US')...")
    try:
        analysis = get_major_indices_options("US")
        print(f"   Analysis result items: {len(analysis)}")
        for item in analysis:
            print(
                f"   - {item.get('ticker')}: {item.get('sentiment')} (PCR: {item.get('pcr', {}).get('oi_pcr')})"
            )
    except Exception as e:
        print(f"   [ERROR] get_major_indices_options error: {e}")


if __name__ == "__main__":
    test_options()
