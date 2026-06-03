import pandas as pd

from src.services import japan_market_conditions as service


def _history(start: float, end: float, volume: float = 100.0) -> pd.DataFrame:
    closes = [start] * 70 + [end]
    volumes = [100.0] * 70 + [volume]
    return pd.DataFrame({"Close": closes, "Volume": volumes})


def test_japan_conditions_use_direct_env_values_and_proxies(monkeypatch):
    monkeypatch.setenv("NIKKEI_JSF_SHORT_BALANCE_BILLION", "9000")
    monkeypatch.setenv("NIKKEI_LEVERAGE_MARGIN_RATIO", "0.8")
    monkeypatch.setenv("NIKKEI_FOREIGN_INVESTOR_NET_BUY_BILLION", "1200")

    def fake_stock_data(ticker, period):
        if ticker == "^N225":
            return _history(100, 110, 150)
        if ticker == "^GSPC":
            return _history(100, 102, 100)
        return _history(100, 99, 100)

    monkeypatch.setattr(service, "get_stock_data", fake_stock_data)

    result = service.build_japan_conditions_context(
        {"WTI Oil": {"change": -2.5}},
        {"markets": {"JP": {"leaders": [{"flow_score": 40}]}}},
    )

    assert result["items"][0]["status"] == "met"
    assert result["items"][1]["status"] == "met"
    assert result["items"][5]["status"] == "met"
    assert result["met_count"] >= 3


def test_japan_conditions_show_unavailable_direct_data(monkeypatch):
    monkeypatch.delenv("NIKKEI_JSF_SHORT_BALANCE_BILLION", raising=False)
    monkeypatch.delenv("NIKKEI_LEVERAGE_MARGIN_RATIO", raising=False)
    monkeypatch.delenv("NIKKEI_FOREIGN_INVESTOR_NET_BUY_BILLION", raising=False)
    monkeypatch.setattr(
        service, "get_stock_data", lambda ticker, period: pd.DataFrame()
    )

    result = service.build_japan_conditions_context()

    assert result["unavailable_count"] >= 2
    assert result["items"][0]["status_label"] == "データ不足"
    assert result["quality_warnings"]
