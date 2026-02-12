import sys
import os
import time
import finnhub

# Add src to path
sys.path.insert(0, os.getcwd())
from src.finnhub_client import get_quote, get_company_profile

# Candidates for migration (Index/Commodity -> ETF/CFD)
CANDIDATES = {
    "S&P 500": ["SPY", "VOO", "IVV", "OANDA:SPX500_USD"],
    "Nasdaq": ["QQQ", "ONEQ"],
    "Dow 30": ["DIA"],
    "Russell 2000": ["IWM"],
    "WTI Oil": ["USO", "OANDA:Wtico_USD"],
    "Gold": ["GLD", "IAU"],
    "Copper": ["CPER", "COPX"],
    "US 10Y Treasury": ["IEF", "TLT", "GOVT"], # IEF is 7-10y, TLT is 20y+
    "Bitcoin": ["BINANCE:BTCUSDT", "BTC-USD"],
    "Ethereum": ["BINANCE:ETHUSDT", "ETH-USD"],
    "USD/JPY": ["FX_IDC:USDJPY", "OANDA:USD_JPY", "PYTH:USDJPY", "BITFINEX:USDJPY"],
    "EUR/USD": ["FX_IDC:EURUSD", "OANDA:EUR_USD"],
    "GBP/USD": ["FX_IDC:GBPUSD", "OANDA:GBP_USD"]
}

def check_symbol(label, symbol):
    print(f"Checking {label} -> {symbol} ...", end=" ")
    try:
        # Quote check
        q = get_quote(symbol)
        if q and q.get("c", 0) > 0:
            print(f"[OK] Price: {q['c']}")
            return True, q['c']
        else:
            print(f"[FAIL] No data (c=0 or None)")
            return False, 0
    except Exception as e:
        print(f"[ERROR] {e}")
        return False, 0

def main():
    # Load .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    print("=== Finnhub Symbol Verification ===")
    
    results = {}
    
    for label, symbols in CANDIDATES.items():
        print(f"\nTarget: {label}")
        found = False
        for sym in symbols:
            valid, price = check_symbol(label, sym)
            if valid:
                results[label] = sym
                found = True
                break # Use the first one that works
            time.sleep(0.5) # Rate limit mitigation
            
        if not found:
            print(f"[WARN] No valid symbol found for {label}")
            results[label] = None

    print("\n=== Summary of Valid Symbols ===")
    for k, v in results.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
