from src.market_config import get_market_config


def test_us_and_jp_share_non_sector_market_configuration():
    us = get_market_config("US")
    jp = get_market_config("JP")

    assert list(us["indices"].keys()) == [
        "S&P 500",
        "Nasdaq 100",
        "Dow 30",
        "Russell 2000",
        "TOPIX",
        "日経平均",
        "Euro 600",
        "Hang Seng",
        "Sensex",
        "KOSPI",
    ]
    assert us["indices"] == jp["indices"]
    assert list(us["treasuries"]) == ["US 10Y Yield", "US 30Y Yield"]
    assert us["volatility"] == {"VIX": "^VIX"}
    assert us["commodities"] == jp["commodities"]
    assert us["forex"] == jp["forex"]
    assert us["crypto"] == jp["crypto"]
    assert "GBP/USD" not in us["forex"]
    assert list(us["crypto"].keys()) == ["Bitcoin"]
    assert "Silver" not in us["commodities"]


def test_jp_sectors_use_next_funds_topix17_etfs():
    jp = get_market_config("JP")

    assert list(jp["sectors"].values()) == [f"{code}.T" for code in range(1617, 1634)]
    assert len(jp["sectors"]) == 17
    assert jp["sectors"]["TOPIX-17 食品"] == "1617.T"
    assert jp["sectors"]["TOPIX-17 不動産"] == "1633.T"
