from types import SimpleNamespace

import pandas as pd


def test_historical_data_status_reports_failed_without_zero_fallback(
    monkeypatch, tmp_path
):
    from src import stock_data_provider
    from src.persistent_cache import PersistentJsonCache

    stock_data_provider.get_historical_data.clear_cache()
    stock_data_provider.get_historical_data_with_status.clear_cache()
    monkeypatch.setattr(
        stock_data_provider,
        "repo_state_cache",
        lambda namespace: PersistentJsonCache(tmp_path, namespace),
    )
    monkeypatch.setattr(
        stock_data_provider,
        "_get_history",
        lambda stock, period: pd.DataFrame(),
    )

    result = stock_data_provider.get_historical_data_with_status("SPY", "1mo")

    assert result.data.empty
    assert result.cache_status == "failed"
    assert result.is_partial is True
    assert result.error


def test_get_stock_info_can_skip_gemini_translation(monkeypatch):
    from src import stock_data_provider

    stock_data_provider.get_stock_info.clear_cache()

    def fake_extract(ticker, info, *, include_summary=True):
        info["name"] = "Example Inc."
        info["sector"] = "Technology"
        info["summary"] = "English business summary."

    monkeypatch.setattr(stock_data_provider, "_extract_yfinance_profile", fake_extract)
    monkeypatch.setattr(stock_data_provider, "is_japanese_stock", lambda ticker: False)
    monkeypatch.setattr(
        stock_data_provider.jquants_client, "is_configured", lambda: False
    )
    monkeypatch.setattr(stock_data_provider, "get_company_finance", lambda ticker: None)
    monkeypatch.setattr(
        stock_data_provider,
        "translate_to_japanese",
        lambda text: (_ for _ in ()).throw(AssertionError("Gemini was called")),
    )

    info = stock_data_provider.get_stock_info("AAPL", translate_summary=False)

    assert info["name"] == "Example Inc."
    assert info["summary"] == "English business summary."


def test_market_monitor_uses_lightweight_valuation_metrics(monkeypatch):
    from src.services import market_dashboard_service as service

    df = pd.DataFrame(
        {
            "Close": [100 + i for i in range(30)],
            "Volume": [1_000 + i for i in range(30)],
        }
    )
    tnx = pd.DataFrame({"Close": [40.0]})
    valuation_calls = []

    def fake_stock_data(ticker, period):
        return tnx if ticker == "^TNX" else df

    def fake_valuation(ticker):
        valuation_calls.append(ticker)
        return {"pe_ratio": 20.0 if ticker == "SPY" else 25.0}

    monkeypatch.setattr(service, "get_stock_data", fake_stock_data)
    monkeypatch.setattr(service, "get_valuation_metrics", fake_valuation)

    monitor = service.build_market_monitor_context(
        [{"ticker": "SPY", "pcr": {"volume_pcr": 0.8}}]
    )

    assert valuation_calls == ["SPY", "QQQ"]
    assert monitor["distribution_spy"]["count"] >= 0
    assert monitor["yield_spread"]["spreads"]["SPY"]["level"] in {
        "green",
        "red",
        "neutral",
    }


def test_theme_download_configures_yfinance_cache(monkeypatch):
    from src import theme_analyst

    calls = []
    monkeypatch.setattr(
        theme_analyst, "configure_yfinance_cache", lambda: calls.append(True)
    )
    monkeypatch.setattr(
        theme_analyst, "get_themes", lambda market_type: {"AI": ["MSFT"]}
    )
    monkeypatch.setattr(
        theme_analyst.yf, "download", lambda *args, **kwargs: pd.DataFrame()
    )

    assert theme_analyst.fetch_and_calculate_all_performances(5, "US") == {}
    assert calls


def test_market_option_summary_formats_price_server_side():
    from src.services.market_presentation_service import (
        OptionSummary,
        format_option_summaries,
    )

    formatted = [
        OptionSummary(**item)
        for item in format_option_summaries(
            [
                {
                    "ticker": "SPY",
                    "current_price": 1234.5,
                    "pcr": {"volume_pcr": 0.9},
                    "gex": None,
                    "iv": 0.2,
                    "max_pain": 1200,
                    "analysis": [],
                    "data_quality": "partial",
                    "quality_warnings": ["Greeks missing"],
                }
            ]
        )
    ]

    assert formatted[0].current_price == 1234.5
    assert formatted[0].current_price_str == "$1,234.50"
    assert formatted[0].net_gex_str == "-"
    assert formatted[0].data_quality == "partial"


def test_market_state_keeps_quality_warnings_out_of_global_error(monkeypatch):
    from frontend.state.market_state import MarketState
    from src.services import provider_health
    from src.services.analysis_context import MarketContext, OptionContext

    monkeypatch.setattr(provider_health, "record_data_results", lambda *args, **_: None)
    monkeypatch.setattr(
        provider_health, "record_option_context", lambda *args, **_: None
    )
    state = SimpleNamespace(error_msg="")
    context = MarketContext(
        market_type="US",
        market_data={"S&P 500": {"ticker": "SPY", "price": 500.0, "change": 0.1}},
        market_config={"indices": {"S&P 500": "SPY"}},
        options=OptionContext(
            status="partial",
            quality_warnings=[
                "MarketData.app preferred fetch unavailable; yfinance fallback is active.",
                "Greeks/Gamma are missing from the option provider; GEX is hidden.",
            ],
        ),
        quality_warnings=[
            "MarketData.app preferred fetch unavailable; yfinance fallback is active."
        ],
    )

    MarketState._apply_market_context(state, context)

    assert state.error_msg == ""
    assert state.option_status == "partial"
