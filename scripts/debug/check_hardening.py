import os
import sys

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.advisor.mean_reversion import MeanReversionAnalyzer
from src.advisor.technical_indicators import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ma_deviation,
    calculate_macd_signal,
    calculate_rsi,
    calculate_support_resistance,
)
from src.news_analyst import generate_flash_summary


def test_technical_indicators():
    print("Testing technical indicators with empty data...")
    empty_series = pd.Series(dtype=float)
    short_series = pd.Series([100, 101, 102])

    print("RSI:", calculate_rsi(short_series))
    print("MA Dev:", calculate_ma_deviation(short_series))
    print("MACD:", calculate_macd_signal(short_series))
    print("BB:", calculate_bollinger_bands(short_series))
    print("ATR:", calculate_atr(short_series, short_series, short_series, 14))
    print("Support:", calculate_support_resistance(empty_series, 20))
    print("Technical indicators passed.")

def test_mean_reversion():
    print("Testing mean reversion with insufficient data...")
    df = pd.DataFrame({"Close": [100]*10, "Open": [100]*10, "High": [100]*10, "Low": [100]*10})
    analyzer = MeanReversionAnalyzer("TEST")
    res = analyzer.analyze(df)
    print("Mean Reversion Result keys:", res.keys())
    print("Mean Reversion passed.")

def test_news_analyst():
    print("Testing news analyst with missing keys...")
    market_data = {
        "S&P 500": {"wrong_key": 100},
        "USD/JPY": {"wrong_key": 150}
    }
    summary = generate_flash_summary(market_data, ["News 1"])
    print("Flash Summary generated successfully:")
    print(summary)

if __name__ == "__main__":
    try:
        test_technical_indicators()
        test_mean_reversion()
        test_news_analyst()
        print("\nAll expected fallback tests passed successfully! No crashes occurred.")
    except Exception as e:
        print(f"\n[CRITICAL] Error during test: {e}")
        import traceback
        traceback.print_exc()

