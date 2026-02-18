import yfinance as yf


def test_nvda_oi():
    ticker = "NVDA"
    print(f"Checking {ticker} options...")
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        if not exps:
            print("No expirations.")
            return

        print(f"Exp: {exps[0]}")
        c = t.option_chain(exps[0]).calls
        print(f"NVDA OI Sum: {c['openInterest'].sum()}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_nvda_oi()
