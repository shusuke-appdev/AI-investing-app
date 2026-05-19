import pandas as pd

from src import market_index_provider


class FakeTicker:
    def __init__(self, ticker):
        self.ticker = ticker

    def history(self, period):
        return pd.DataFrame({"Close": [100.0, 105.0]})


def test_market_indices_fall_back_to_yfinance_when_finnhub_quote_empty(monkeypatch):
    market_index_provider.get_market_indices.clear_cache()
    monkeypatch.setattr(
        market_index_provider,
        "get_market_config",
        lambda market_type: {
            "indices": {},
            "sectors": {"Technology": "XLK"},
            "commodities": {},
            "crypto": {},
            "treasuries": {},
            "forex": {},
        },
    )
    monkeypatch.setattr(market_index_provider, "is_configured", lambda: True)
    monkeypatch.setattr(
        market_index_provider, "_finnhub_get_quote", lambda ticker: None
    )
    monkeypatch.setattr(market_index_provider.yf, "Ticker", FakeTicker)

    result = market_index_provider.get_market_indices("US")

    assert result["Technology"] == {"price": 105.0, "change": 5.0, "ticker": "XLK"}
