import pandas as pd

from src.services import stock_dashboard_service as service


def _price_history() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": [100.0, 101.0, 102.0],
            "Volume": [1_000_000, 1_100_000, 1_200_000],
        },
        index=pd.date_range("2026-01-01", periods=3),
    )


def test_stock_dashboard_profile_gap_is_warning_not_fatal(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_stock_info",
        lambda ticker, translate_summary=False: {
            "name": ticker,
            "ticker": ticker,
            "sector": "N/A",
            "industry": "N/A",
            "summary": "N/A",
            "market_cap": None,
            "pe_ratio": None,
            "dividend_yield": None,
            "current_price": None,
        },
    )
    monkeypatch.setattr(
        service, "get_stock_data", lambda ticker, period: _price_history()
    )
    monkeypatch.setattr(
        service,
        "get_stock_news_with_status",
        lambda ticker, max_items: {
            "items": [],
            "source_status": "fallback",
            "error_reason": "",
        },
    )
    monkeypatch.setattr(
        service,
        "analyze_technical",
        lambda ticker, period: {"overall_signal": "Hold", "overall_score": 50},
    )
    monkeypatch.setattr(
        service,
        "evaluate_smart_criteria",
        lambda ticker, info, trend: {
            "all_met": False,
            "S": {"met": False, "desc": "Sales", "value": "データなし"},
        },
    )
    monkeypatch.setattr(
        service, "generate_probabilistic_stock_signal", lambda *args: object()
    )
    monkeypatch.setattr(
        service,
        "signal_to_dict",
        lambda signal: {
            "signal_label": "Insufficient data",
            "suggested_action": "Watch",
        },
    )
    monkeypatch.setattr(
        service,
        "generate_trend_follow_diagnostics",
        lambda *args: object(),
    )
    monkeypatch.setattr(
        service,
        "trend_follow_to_dict",
        lambda diagnostics: {
            "diagnostic_rating": "Unavailable",
            "rating_display": "Unavailable",
            "data_quality": {"status": "insufficient_data"},
            "warnings": ["Insufficient daily price history."],
        },
    )
    monkeypatch.setattr(service, "evaluate_trade_setup", lambda *args: object())
    monkeypatch.setattr(
        service,
        "trade_setup_to_dict",
        lambda setup: {
            "status": "wait",
            "grade": "B",
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        service,
        "evaluate_stock_sector_theme_context",
        lambda ticker, info, market_type="US", **kwargs: {
            "combined_rating": "weak",
            "fundamental_advantage": False,
            "flow_advantage": False,
            "themes": ["Technology"],
            "rationale": "No edge.",
        },
    )

    context = service.build_stock_dashboard_context("PLTR")

    assert context.error_message == ""
    assert "企業概要の一部" in context.profile_warning
    assert context.display_info == {
        "name": "PLTR",
        "exchange": "",
        "sector": "N/A",
        "market_cap": "N/A",
        "pe_ratio": "N/A",
        "dividend_yield": "N/A",
        "summary": "概要情報がありません。",
    }
    assert len(context.chart_data) == 3
    assert context.trend_follow_diagnostics["diagnostic_rating"] == "Unavailable"
    assert context.trade_setup["status"] == "wait"
    assert context.sector_theme_context["combined_rating"] == "weak"
    assert context.stock_signal_context["smart_criteria"]["all_met"] is False
    assert context.stock_signal_context["news_headlines"] == []
    assert context.stock_signal_context["provenance"]
    assert any(item.kind.value == "proxy" for item in context.provenance)
    trend_status = next(
        item for item in context.data_status if item.name == "trend_follow_diagnostics"
    )
    assert trend_status.is_partial is True
    profile_status = next(
        item for item in context.data_status if item.name == "stock_profile"
    )
    assert profile_status.is_partial is True


def test_stock_dashboard_display_info_formats_core_metrics():
    display = service._build_display_info(
        "PLTR",
        {
            "name": "Palantir Technologies Inc.",
            "exchange": "NMS",
            "sector": "Technology",
            "summary": "Builds software platforms.",
            "market_cap": 328_791_326_720,
            "pe_ratio": 154.10112,
            "dividend_yield": 0.42,
        },
    )

    assert display["name"] == "Palantir Technologies Inc."
    assert display["market_cap"] == "$328.79B"
    assert display["pe_ratio"] == "154.10"
    assert display["dividend_yield"] == "0.42%"


def test_stock_dashboard_keeps_partial_results_when_optional_diagnostic_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "get_stock_info",
        lambda ticker, translate_summary=False: {"ticker": ticker, "name": "Test"},
    )
    monkeypatch.setattr(service, "get_stock_data", lambda *args: _price_history())
    monkeypatch.setattr(
        service,
        "get_stock_news_with_status",
        lambda *args: {"items": [], "source_status": "available", "error_reason": ""},
    )
    monkeypatch.setattr(service, "analyze_technical", lambda *args: {"score": 1})
    monkeypatch.setattr(service, "evaluate_smart_criteria", lambda *args: {})
    monkeypatch.setattr(
        service,
        "generate_probabilistic_stock_signal",
        lambda *args: (_ for _ in ()).throw(RuntimeError("model unavailable")),
    )
    monkeypatch.setattr(
        service, "generate_trend_follow_diagnostics", lambda *args: object()
    )
    monkeypatch.setattr(
        service,
        "trend_follow_to_dict",
        lambda value: {"data_quality": {"status": "ok"}, "warnings": []},
    )
    monkeypatch.setattr(
        service, "analyze_fomo_volatility_regime", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(service, "evaluate_trade_setup", lambda *args: object())
    monkeypatch.setattr(
        service, "trade_setup_to_dict", lambda value: {"status": "wait", "warnings": []}
    )
    monkeypatch.setattr(
        service, "evaluate_stock_sector_theme_context", lambda *args, **kwargs: {}
    )

    context = service.build_stock_dashboard_context("TEST")

    assert context.info["ticker"] == "TEST"
    assert context.chart_data
    assert context.probabilistic_signal == {}
    assert any("model unavailable" in warning for warning in context.quality_warnings)
    status = next(
        item for item in context.data_status if item.name == "probabilistic_signal"
    )
    assert status.cache_status == "failed"


def test_stock_dashboard_reuses_shared_target_and_benchmark_history(monkeypatch):
    calls: list[tuple[str, str]] = []
    sector_kwargs = {}

    def history(ticker: str, period: str):
        calls.append((ticker, period))
        return _price_history()

    monkeypatch.setattr(service, "get_stock_data", history)
    monkeypatch.setattr(
        service,
        "get_stock_info",
        lambda ticker, translate_summary=False: {"ticker": ticker, "name": "Test"},
    )
    monkeypatch.setattr(
        service,
        "get_stock_news_with_status",
        lambda *args: {"items": [], "source_status": "available", "error_reason": ""},
    )
    monkeypatch.setattr(service, "analyze_technical", lambda *args: {})
    monkeypatch.setattr(service, "evaluate_smart_criteria", lambda *args: {})
    monkeypatch.setattr(
        service, "generate_probabilistic_stock_signal", lambda *args: {}
    )
    monkeypatch.setattr(service, "signal_to_dict", lambda value: value)
    monkeypatch.setattr(service, "generate_trend_follow_diagnostics", lambda *args: {})
    monkeypatch.setattr(service, "trend_follow_to_dict", lambda value: value)
    monkeypatch.setattr(
        service, "analyze_fomo_volatility_regime", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(service, "evaluate_trade_setup", lambda *args: {})
    monkeypatch.setattr(service, "trade_setup_to_dict", lambda value: value)

    def sector_context(*args, **kwargs):
        sector_kwargs.update(kwargs)
        return {}

    monkeypatch.setattr(service, "evaluate_stock_sector_theme_context", sector_context)

    service.build_stock_dashboard_context("TEST")

    assert calls.count(("TEST", "5y")) == 1
    assert calls.count(("SPY", "5y")) == 1
    assert calls == [("TEST", "5y"), ("SPY", "5y")]
    assert sector_kwargs["include_theme_options"] is True
    assert sector_kwargs["theme_options_cache_only"] is True
