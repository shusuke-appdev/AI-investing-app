import pandas as pd
import yfinance as yf

symbols = ["^VIX9D", "^VIX", "^VIX3M", "^VIX6M", "^VIX1Y", "^VVIX", "^SKEW"]
for sym in symbols:
    df = yf.download(sym, period="1mo", progress=False)
    if not df.empty:
        print(f"{sym}: OK, latest close = {df['Close'].iloc[-1].item():.2f}")
    else:
        print(f"{sym}: Data not found")
