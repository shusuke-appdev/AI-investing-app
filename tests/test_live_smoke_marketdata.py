from dataclasses import dataclass

import pandas as pd


@dataclass
class _FakeMarketDataResult:
    resolved_expiration: str
    resolved_dte: int
    data_as_of: str = "2026-07-02T20:00:00+00:00"
    credits_consumed: int = 0
    credits_remaining: int = 9999

    @property
    def calls(self) -> pd.DataFrame:
        return pd.DataFrame({"strike": [600], "impliedVolatility": [0.1]})

    @property
    def puts(self) -> pd.DataFrame:
        return pd.DataFrame({"strike": [600], "impliedVolatility": [0.12]})


def test_marketdata_live_smoke_reports_app_term_structure(monkeypatch):
    from scripts import live_smoke
    from src import marketdata_option_provider, option_analyst

    fetch_calls = []

    def fake_fetch(ticker, **kwargs):
        fetch_calls.append((ticker, kwargs))
        target_dte = kwargs.get("target_dte")
        if target_dte == 7:
            return _FakeMarketDataResult("2026-07-10", 8)
        if target_dte == 30:
            return _FakeMarketDataResult("2026-07-31", 29)
        return _FakeMarketDataResult("2026-07-06", 4)

    def fake_analysis(ticker, *, allow_marketdata):
        assert ticker == "SPY"
        assert allow_marketdata is True
        return {
            "term_structure": {"summary": "現在IV=7.2% / 1W IV=11.0% / 1M IV=13.7%"},
            "horizons": [
                {
                    "key": "current",
                    "source": "marketdata.app_cache",
                    "provider_active": True,
                    "resolved_expiration": "2026-07-06",
                    "resolved_dte": 4,
                    "iv": 0.072,
                    "data_as_of": "2026-07-02T20:00:00+00:00",
                },
                {
                    "key": "one_week",
                    "source": "marketdata.app_cache",
                    "provider_active": True,
                    "resolved_expiration": "2026-07-10",
                    "resolved_dte": 8,
                    "iv": 0.11,
                    "data_as_of": "2026-07-02T20:00:00+00:00",
                },
                {
                    "key": "one_month",
                    "source": "marketdata.app_cache",
                    "provider_active": True,
                    "resolved_expiration": "2026-07-31",
                    "resolved_dte": 29,
                    "iv": 0.137,
                    "data_as_of": "2026-07-02T20:00:00+00:00",
                },
            ],
        }

    monkeypatch.setenv("MARKETDATA_TOKEN", "secret")
    monkeypatch.setenv("MARKETDATA_OPTIONS_MODE", "preferred")
    monkeypatch.setattr(
        marketdata_option_provider, "fetch_marketdata_option_chain", fake_fetch
    )
    monkeypatch.setattr(option_analyst, "analyze_option_sentiment", fake_analysis)

    detail = live_smoke._marketdata_options_check(
        tickers=["SPY"], min_dte=1, horizon_dtes=[7, 30]
    )

    assert "SPY:term_structure=現在IV=7.2% / 1W IV=11.0% / 1M IV=13.7%" in detail
    assert "calls=1/100 puts=1/100 side_cap_reached=false" in detail
    assert "current@2026-07-06/dte=4/iv=7.2%/as_of=2026-07-02T20:00:00+00:00" in detail
    assert [call[1].get("target_dte") for call in fetch_calls] == [None, 7, 30]


def test_marketdata_live_smoke_degrades_when_app_term_structure_is_missing(
    monkeypatch,
):
    from scripts import live_smoke
    from src import marketdata_option_provider, option_analyst

    def fake_fetch(_ticker, **kwargs):
        target_dte = kwargs.get("target_dte")
        if target_dte == 7:
            return _FakeMarketDataResult("2026-07-10", 8)
        if target_dte == 30:
            return _FakeMarketDataResult("2026-07-31", 29)
        return _FakeMarketDataResult("2026-07-06", 4)

    monkeypatch.setenv("MARKETDATA_TOKEN", "secret")
    monkeypatch.setenv("MARKETDATA_OPTIONS_MODE", "preferred")
    monkeypatch.setattr(
        marketdata_option_provider, "fetch_marketdata_option_chain", fake_fetch
    )
    monkeypatch.setattr(
        option_analyst,
        "analyze_option_sentiment",
        lambda _ticker, *, allow_marketdata: {
            "term_structure": {},
            "horizons": [
                {"key": "current", "source": "marketdata.app", "provider_active": True}
            ],
        },
    )

    detail = live_smoke._marketdata_options_check(
        tickers=["SPY"], min_dte=1, horizon_dtes=[7, 30]
    )

    assert detail.startswith("DEGRADED:")
    assert "SPY:term_structure_missing=one_week,one_month" in detail
