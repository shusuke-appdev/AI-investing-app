import pandas as pd

from src.services import sector_flow_service as service


def _history(start: float, end: float, volume: float = 100.0) -> pd.DataFrame:
    closes = [start] * 40 + [end]
    volumes = [100.0] * 40 + [volume]
    return pd.DataFrame({"Close": closes, "Volume": volumes})


def test_sector_flow_ranks_confirmed_inflow(monkeypatch):
    monkeypatch.setattr(
        service,
        "_candidate_groups",
        lambda market_type: {"AI": ["AAA"], "Energy": ["BBB"]},
    )

    def fake_stock_data(ticker, period):
        if ticker in {"SPY", "^N225"}:
            return _history(100, 101, 100)
        if ticker == "AAA":
            return _history(100, 112, 180)
        return _history(100, 95, 90)

    monkeypatch.setattr(service, "get_stock_data", fake_stock_data)

    result = service.build_sector_flow_context()

    us_top = result["markets"]["US"]["leaders"][0]
    assert us_top["theme"] == "AI"
    assert us_top["flow_score"] > 25
    assert us_top["action"] in {"乗る候補", "押し目待ち"}
    assert result["primary_market"] == "US"


def test_cross_market_context_keeps_us_primary():
    flow = {
        "markets": {
            "US": {"leaders": [{"theme": "Tech", "flow_score": 60}]},
            "JP": {"leaders": [{"theme": "半導体", "flow_score": 20}]},
        }
    }

    result = service.build_cross_market_context(flow)

    assert result["primary_market"] == "US"
    assert "US flow leadership" in result["stance"]
