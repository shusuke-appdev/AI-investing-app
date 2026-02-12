import sys
import os
import time

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from finnhub_client import get_quote

SECTORS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Consumer Disc": "XLY",
    "Communication": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB"
}

def main():
    print("=== Checking Sector ETFs on Finnhub ===")
    success_count = 0
    for name, ticker in SECTORS.items():
        print(f"Checking {name} ({ticker})...", end=" ")
        try:
            q = get_quote(ticker)
            if q and q.get("c", 0) > 0:
                print(f"[OK] {q['c']}")
                success_count += 1
            else:
                print(f"[FAIL] {q}")
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(0.2) # Avoid rate limit
        
    print(f"\nResult: {success_count}/{len(SECTORS)} sectors available on Finnhub.")

if __name__ == "__main__":
    main()
