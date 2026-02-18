import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from finnhub_client import get_quote

sys.path.insert(0, os.getcwd())

# Load .env
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


def main():
    ticker = "AAPL"
    print(f"Testing get_quote for {ticker}...")
    try:
        q = get_quote(ticker)
        print(f"Result: {q}")
        if q and q.get("c"):
            print("Quote Fetch Successful")
        else:
            print("Quote Fetch Failed or Empty")
    except Exception as e:
        print(f"Exception: {e}")


if __name__ == "__main__":
    main()
