import os
import sys

import yfinance as yf

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_next_expiration():
    ticker = "SPY"
    print(f"Checking {ticker} options...")
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        if len(exps) < 2:
            print("Not enough expirations to test.")
            return

        print(f"1st Exp (Today?): {exps[0]}")
        c1 = t.option_chain(exps[0]).calls
        print(f"   OI Sum: {c1['openInterest'].sum()}")

        print(f"2nd Exp (Next): {exps[1]}")
        c2 = t.option_chain(exps[1]).calls
        print(f"   OI Sum: {c2['openInterest'].sum()}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_next_expiration()
