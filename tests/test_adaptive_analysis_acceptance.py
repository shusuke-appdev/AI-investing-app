import numpy as np
import pandas as pd
import pytest

from src.services.fundamental_profile_service import (
    evaluate_fundamental_profile,
    select_sector_profile,
)
from src.services.market_strategy_service import build_important_levels


def _history(rows: int = 126) -> pd.DataFrame:
    close = np.linspace(100, 120, rows)
    return pd.DataFrame(
        {
            "Open": close - 1,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": np.linspace(1_000_000, 2_000_000, rows),
        }
    )


@pytest.mark.parametrize(
    ("ticker", "industry", "expected"),
    [
        ("NVDA", "Semiconductors", "semiconductor"),
        ("JPM", "Banks - Diversified", "bank"),
        ("O", "Retail REIT", "reit"),
        ("7203.T", "Auto Manufacturers", "general"),
        ("8306.T", "銀行業", "bank"),
        ("BIOTECH", "Biotechnology", "pharma_biotech"),
    ],
)
def test_acceptance_universe_selects_business_model_profile(
    ticker: str, industry: str, expected: str
):
    result = select_sector_profile({"ticker": ticker, "industry": industry})

    assert result["key"] == expected


def test_precommercial_biotech_without_pipeline_is_unavailable():
    result = evaluate_fundamental_profile(
        "BIOTECH",
        {
            "market_cap": 2_000_000_000,
            "industry": "Biotechnology",
            "revenueGrowth": -20.0,
            "earningsGrowth": -30.0,
            "operatingMargins": -120.0,
            "grossMargins": 70.0,
            "priceToBook": 4.0,
            "forward_pe": 30.0,
            "totalCash": 300_000_000,
            "freeCashflow": -200_000_000,
        },
    )

    assert result["status"] == "unavailable"
    assert any("pipeline" in reason.lower() for reason in result["missing_reasons"])


def test_jp_market_important_levels_use_two_index_etf_proxies(monkeypatch):
    monkeypatch.setattr(
        "src.services.market_strategy_service.get_stock_data",
        lambda ticker, period: _history(),
    )

    result = build_important_levels("JP")

    assert [item["ticker"] for item in result["items"]] == ["1306.T", "1321.T"]
    assert all(
        item["volume_profile"]["status"] == "available" for item in result["items"]
    )
    assert all("ETF proxy" in item["proxy_note"] for item in result["items"])
