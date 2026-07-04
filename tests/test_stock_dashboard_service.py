import time

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
            "T": {
                "met": False,
                "status": "unknown",
                "value": "市場状態未更新",
            },
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
    monkeypatch.setattr(
        service,
        "evaluate_fundamental_profile",
        lambda *args, **kwargs: {
            "status": "partial",
            "smart_applicability": "growth_proxy",
            "missing_reasons": ["ROE missing"],
        },
    )
    monkeypatch.setattr(
        service,
        "build_volume_profile",
        lambda *args, **kwargs: {
            "status": "insufficient_data",
            "reason": "needs 60 sessions",
        },
    )
    monkeypatch.setattr(
        service,
        "evaluate_purchase_evidence",
        lambda **kwargs: {
            "status": "insufficient_data",
            "missing_reasons": ["fundamental missing"],
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
    status_by_name = {item.name: item for item in context.data_status}
    assert status_by_name["smart_criteria"].source == "local_smart_proxy"
    assert status_by_name["smart_criteria"].is_partial is True
    assert "市場状態未更新" in status_by_name["smart_criteria"].error
    assert status_by_name["fundamental_profile"].is_partial is True
    assert "ROE missing" in status_by_name["fundamental_profile"].error
    assert status_by_name["volume_profile"].is_partial is True
    assert "needs 60 sessions" in status_by_name["volume_profile"].error
    assert status_by_name["purchase_evidence"].is_partial is True
    assert "fundamental missing" in status_by_name["purchase_evidence"].error
    health_by_feature = {
        item["feature"]: item for item in context.purchase_evidence_health
    }
    assert health_by_feature["technical_score"]["status_key"] == "unavailable"
    assert health_by_feature["adaptive_fundamental"]["status_key"] == "unavailable"
    assert health_by_feature["theme_rank"]["status_key"] == "unavailable"
    assert (
        context.stock_signal_context["purchase_evidence_health"]
        == context.purchase_evidence_health
    )


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


def test_stock_dashboard_times_out_slow_optional_diagnostic(monkeypatch):
    monkeypatch.setattr(service, "STOCK_OPTIONAL_ANALYSIS_TIMEOUT_SECONDS", 0.01)
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

    def slow_probabilistic_signal(*args):
        time.sleep(0.2)
        return {}

    monkeypatch.setattr(
        service, "generate_probabilistic_stock_signal", slow_probabilistic_signal
    )
    monkeypatch.setattr(service, "signal_to_dict", lambda value: value)
    monkeypatch.setattr(service, "generate_trend_follow_diagnostics", lambda *args: {})
    monkeypatch.setattr(service, "trend_follow_to_dict", lambda value: value)
    monkeypatch.setattr(
        service, "analyze_fomo_volatility_regime", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(service, "evaluate_trade_setup", lambda *args: {})
    monkeypatch.setattr(service, "trade_setup_to_dict", lambda value: value)
    monkeypatch.setattr(
        service,
        "evaluate_fundamental_profile",
        lambda *args, **kwargs: {"smart_applicability": "growth_proxy"},
    )
    monkeypatch.setattr(service, "build_volume_profile", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        service, "evaluate_stock_sector_theme_context", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        service, "build_japan_supply_demand_context", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(service, "evaluate_purchase_evidence", lambda **kwargs: {})

    started = time.perf_counter()
    context = service.build_stock_dashboard_context("TEST")

    assert time.perf_counter() - started < 0.15
    assert context.info["ticker"] == "TEST"
    assert context.chart_data
    assert context.probabilistic_signal == {}
    assert any(
        "probabilistic_signal timed out" in item for item in context.quality_warnings
    )
    status = next(
        item for item in context.data_status if item.name == "probabilistic_signal"
    )
    assert status.cache_status == "failed"
    assert status.is_partial is True


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
