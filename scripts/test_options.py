import yfinance as yf


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
            print(
                f"yfinance call columns: {opt.calls.columns.tolist() if not opt.calls.empty else 'Empty'}"
            )
    except Exception as e:
        print(f"yfinance error: {e}")


if __name__ == "__main__":
    test_options()
