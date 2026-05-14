import os

import yfinance as yf
from openbb import obb

# Disable OpenBB auto build to prevent permissions errors
os.environ["OPENBB_AUTO_BUILD"] = "False"


def test_options():
    ticker = "SPY"
    print("Testing yfinance...")
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        print(
            f"yfinance expirations for {ticker}: {expirations[:5] if expirations else 'None'}"
        )
        if expirations:
            opt = stock.option_chain(expirations[0])
            print(f"yfinance calls shape: {opt.calls.shape}")
            # check yf columns to compare with OpenBB
            print(
                f"yfinance call columns: {opt.calls.columns.tolist() if not opt.calls.empty else 'Empty'}"
            )
    except Exception as e:
        print(f"yfinance error: {e}")

    print("\nTesting OpenBB...")
    try:
        # Get options chains from OpenBB (using yfinance provider as default is often intrinio/fmp which may need keys)
        chains = obb.equity.options.chains(symbol=ticker, provider="yfinance")
        df = chains.to_df()
        print(f"OpenBB options shape: {df.shape}")
        if not df.empty:
            print(f"OpenBB options columns: {df.columns.tolist()}")
            # display sample row
            print(f"OpenBB sample:\n{df.iloc[0]}")
    except Exception as e:
        print(f"OpenBB error: {e}")


if __name__ == "__main__":
    test_options()
