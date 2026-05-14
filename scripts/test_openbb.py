from openbb import obb


def test_openbb():
    try:
        # Quote
        quote = obb.equity.price.quote(symbol="AAPL", provider="yfinance")
        print("Quote:", quote.to_dict())

        # Historical
        hist = obb.equity.price.historical(symbol="AAPL", provider="yfinance")
        # limit just to see structure
        print("Historical columns:", hist.to_df().columns)

        # Profile
        profile = obb.equity.profile(symbol="AAPL", provider="yfinance")
        print("Profile Keys:", profile.to_dict().keys() if profile else "No profile")

        # Metrics
        metrics = obb.equity.fundamental.metrics(symbol="AAPL", provider="yfinance")
        print("Metrics:", metrics.to_dict() if metrics else "No metrics")

    except Exception as e:
        print(f"Error openbb: {e}")


if __name__ == "__main__":
    test_openbb()
