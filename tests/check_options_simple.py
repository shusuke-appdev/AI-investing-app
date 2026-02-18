import os
import sys
from datetime import datetime

import yfinance as yf

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# Only test options for now as it seemed to hang
def test_options_simple():
    print(f"Current System Time: {datetime.now()}")
    print("\n--- Testing Option Data Quality (OI Check) - SPY Only ---")
    ticker = "SPY"

    print(f"Checking {ticker}...")
    try:
        t = yf.Ticker(ticker)
        print("Fetching options list...")
        exps = t.options
        if not exps:
            print(f"   [FAIL] No expirations for {ticker}")
            return

        print(f"First Expiration: {exps[0]}")

        # Check first expiration
        print("Fetching option chain...")
        chain = t.option_chain(exps[0])
        calls = chain.calls

        # Check OI
        print("Calculating OI...")
        oi_sum = calls["openInterest"].sum()
        vol_sum = calls["volume"].sum()

        print(f"   Exp: {exps[0]} | Calls OI Sum: {oi_sum} | Volume Sum: {vol_sum}")

        if oi_sum == 0:
            print("   [CRITICAL] Open Interest is ZERO.")
        else:
            print("   [OK] Open Interest seems populated.")

    except Exception as e:
        print(f"   [ERROR] {e}")


if __name__ == "__main__":
    test_options_simple()
