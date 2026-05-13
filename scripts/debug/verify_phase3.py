import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.advisor.minervini_analyzer import detect_follow_through_day
from src.market_index_provider import get_market_indices
from src.option_data_provider import get_option_chain
from src.stock_data_provider import get_historical_data


def test_all():
    print("--- OPTIONS ---")
    opt = get_option_chain('SPY')
    if opt:
        calls, puts = opt
        print(f"Option fetch successful! Calls: {len(calls)}, Puts: {len(puts)}")
        if not calls.empty:
            print(f"Sample Strike: {calls['strike'].iloc[0]}, Volume: {calls['volume'].iloc[0]}")
    else:
        print("Option fetch FAILED (returned None)")

    print("\n--- INDICES (Commodities) ---")
    indices = get_market_indices("US")
    for k in ["WTI Oil", "Gold", "Copper", "S&P 500 (ETF)"]:
        print(f"{k}: {indices.get(k)}")

    print("\n--- FTD ALERT ---")
    df = get_historical_data('SPY', '1y')
    print("Recent drawdowns etc.")
    print(detect_follow_through_day(df))

if __name__ == "__main__":
    test_all()
