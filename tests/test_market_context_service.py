from src.services import market_analyst_service
from src.services import market_dashboard_service as service
from src.services.analysis_context import MarketContext, OptionContext


def _monitor_payload():
    return {
        "distribution_spy": {"count": 2, "status": "normal", "level": "green"},
        "distribution_ndx": {"count": 3, "status": "normal", "level": "green"},
        "climax": {"is_climax": False, "warnings": [], "level": "normal"},
        "yield_spread": {
            "yield_10y": 4.0,
            "spreads": {},
            "overall_status": "neutral",
            "warnings": [],
        },
    }


def test_build_market_context_collects_monitoring_inputs(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_market_indices",
        lambda market_type: {"S&P 500": {"ticker": "SPY", "price": 500, "change": 1}},
    )
    monkeypatch.setattr(
        service, "get_market_config", lambda market_type: {"indices": {"SPY": "SPY"}}
    )
    monkeypatch.setattr(
        service,
        "get_major_indices_options",
        lambda market_type: [{"ticker": "SPY", "pcr": {"volume_pcr": 0.9}}],
    )
    monkeypatch.setattr(
        service,
        "evaluate_market_environment",
        lambda market_type, options: {
            "status": "Neutral",
            "score": 0.1,
            "signals": [{"name": "Trend", "score": 0.2, "rationale": "Stable"}],
        },
    )
    monkeypatch.setattr(
        service,
        "analyze_market_structure",
        lambda ticker: {
            "vrp": 0.03,
            "cta_proxy": {"score": 10, "extremity": "Neutral"},
            "liquidity": {"status": "Normal"},
            "unwind_level": "Low",
        },
    )
    monkeypatch.setattr(
        service,
        "get_momentum_themes",
        lambda market_type: {"Short": [{"theme": "AI", "performance": 3.2}]},
    )
    monkeypatch.setattr(
        service, "build_market_monitor_context", lambda options: _monitor_payload()
    )

    context = service.build_market_context("US")

    assert context.market_data["S&P 500"]["ticker"] == "SPY"
    assert context.options.items[0]["ticker"] == "SPY"
    assert context.evaluation["status"] == "Neutral"
    assert context.monitor["distribution_spy"]["count"] == 2
    assert "Market environment" in service.format_market_context_for_ai(context)


def test_build_market_context_keeps_partial_data_when_options_fail(monkeypatch):
    monkeypatch.setattr(service, "get_market_indices", lambda market_type: {"SPY": {}})
    monkeypatch.setattr(service, "get_market_config", lambda market_type: {})
    monkeypatch.setattr(
        service,
        "get_major_indices_options",
        lambda market_type: (_ for _ in ()).throw(RuntimeError("rate limited")),
    )
    monkeypatch.setattr(
        service,
        "evaluate_market_environment",
        lambda market_type, options: {"status": "Neutral", "score": 0, "signals": []},
    )
    monkeypatch.setattr(service, "analyze_market_structure", lambda ticker: {})
    monkeypatch.setattr(service, "get_momentum_themes", lambda market_type: {})
    monkeypatch.setattr(
        service, "build_market_monitor_context", lambda options: _monitor_payload()
    )

    context = service.build_market_context("US")

    assert context.market_data == {"SPY": {}}
    assert context.options.items == []
    assert "Option analysis failed" in context.options.error_message


def test_market_ai_report_reuses_supplied_market_context(monkeypatch):
    context = MarketContext(
        market_type="US",
        market_data={"S&P 500": {"ticker": "SPY", "price": 500, "change": 1}},
        options=OptionContext(items=[{"ticker": "SPY"}]),
        evaluation={
            "status": "Bullish",
            "score": 0.4,
            "signals": [{"name": "Trend", "score": 0.6, "rationale": "Above MAs"}],
        },
        microstructure={
            "vrp": 0.04,
            "cta_proxy": {"extremity": "Long"},
            "liquidity": {"status": "Normal"},
            "unwind_level": "Low",
        },
        momentum={"Short": [{"theme": "AI", "performance": 2.5}]},
        monitor=_monitor_payload(),
    )
    captured = {}

    monkeypatch.setattr(
        market_analyst_service,
        "get_market_config",
        lambda market_type: {"ai_analysis_targets": [], "news_keywords": []},
    )
    monkeypatch.setattr(
        market_analyst_service, "generate_dynamic_search_queries", lambda *args, **_: []
    )
    monkeypatch.setattr(
        market_analyst_service, "get_aggregated_news", lambda **kwargs: []
    )
    monkeypatch.setattr(
        market_analyst_service,
        "merge_with_finnhub_news",
        lambda articles, finnhub_news, max_total: [],
    )
    monkeypatch.setattr(market_analyst_service, "get_ranked_themes", lambda period: [])
    monkeypatch.setattr(
        market_analyst_service,
        "get_major_indices_options",
        lambda market_type: (_ for _ in ()).throw(AssertionError("should not fetch")),
    )

    def fake_recap(market_data, news, options, **kwargs):
        captured["market_data"] = market_data
        captured["options"] = options
        captured["advanced"] = kwargs["advanced_tech_analysis"]
        return "ok"

    monkeypatch.setattr(market_analyst_service, "generate_market_recap", fake_recap)

    result = market_analyst_service.generate_market_analysis_report(
        "US", market_context=context.to_dict()
    )

    assert result == "ok"
    assert captured["options"] == [{"ticker": "SPY"}]
    assert captured["market_data"]["S&P 500"]["ticker"] == "SPY"
    assert "Market environment: Bullish" in captured["advanced"]
