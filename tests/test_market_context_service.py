import threading
import time
from dataclasses import replace

import pandas as pd

from src.persistent_cache import PersistentJsonCache
from src.services import market_analyst_service
from src.services import market_dashboard_service as service
from src.services.analysis_context import DataResult, MarketContext, OptionContext


def test_market_monitor_accepts_explicit_dependencies(monkeypatch):
    from src.services import market_dashboard_service as service
    from src.services.market_dashboard_workflows import (
        _workflow_dependencies,
        build_market_monitor_context,
    )

    monkeypatch.setattr(
        service,
        "get_stock_data",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("historical facade dependency was used")
        ),
    )
    calls: list[tuple[str, str]] = []

    def fake_stock_data(ticker: str, period: str):
        calls.append((ticker, period))
        if ticker == "^TNX":
            return pd.DataFrame({"Close": [40.0]})
        return pd.DataFrame({"Close": [100.0], "Volume": [1_000.0]})

    dependencies = replace(
        _workflow_dependencies(),
        get_stock_data=fake_stock_data,
        track_distribution_days=lambda _: {"count": 0},
        detect_market_climax=lambda *_: {"is_climax": False},
        get_valuation_metrics=lambda ticker: {
            "pe_ratio": 20.0 if ticker == "SPY" else 25.0
        },
        evaluate_yield_spread=lambda value, pe: {
            "yield_10y": value,
            "pe": pe,
        },
    )

    result = build_market_monitor_context([], dependencies=dependencies)

    assert calls == [("SPY", "6mo"), ("^NDX", "6mo"), ("^TNX", "5d")]
    assert result["yield_spread"]["yield_10y"] == 4.0


def test_option_context_accepts_explicit_dependencies(monkeypatch):
    from src.services import market_dashboard_service as service
    from src.services.market_dashboard_support import (
        _build_option_context,
        _support_dependencies,
    )

    monkeypatch.setattr(
        service,
        "get_major_indices_option_status",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("historical facade dependency was used")
        ),
    )
    dependencies = replace(
        _support_dependencies(),
        get_major_indices_option_status=lambda _: {
            "status": "available",
            "source": "injected",
            "items": [{"ticker": "SPY"}],
        },
    )

    result = _build_option_context("US", dependencies=dependencies)

    assert result.status == "available"
    assert result.source == "injected"
    assert result.items == [{"ticker": "SPY"}]


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


def _sector_flow_payload():
    return {
        "summary": "米国: 情報技術(+50.0)",
        "markets": {
            "US": {
                "leaders": [
                    {
                        "theme": "情報技術",
                        "flow_score": 50.0,
                        "confidence": "高",
                        "continuation": "高",
                        "action": "乗る候補",
                    }
                ]
            },
        },
        "quality_warnings": [],
    }


def _japan_conditions_payload():
    return {
        "summary": "総合 45% / 達成 1件 / 代理 4件 / データ不足 1件",
        "score": 0.45,
        "score_label": "中立",
        "unavailable_count": 1,
        "quality_warnings": [
            "Nikkei conditions have 1 unavailable direct data points."
        ],
        "items": [
            {
                "condition_no": 1,
                "status_label": "データ不足",
                "value": "-",
                "evidence": "missing",
            }
        ],
    }


def _credit_stress_payload():
    return {
        "status": "equity_adjustment",
        "status_label": "通常調整寄り",
        "level": "green",
        "summary": "信用市場への同時伝染はまだ確認されていません。",
        "rapid_stress": False,
        "indicators": [
            {
                "series_id": "BAA10Y",
                "label": "BAA信用スプレッド",
                "latest": 1.5,
                "latest_date": "2026-05-01",
                "delta_3m": 0.1,
                "z_score": 0.2,
                "is_hot": False,
                "level": "green",
            }
        ],
        "confirmations": [],
        "warnings": [],
        "source": "test",
        "fetched_at": "2026-05-01T00:00:00+00:00",
    }


def _flow_monitor_payload():
    return {
        "status": "risk_on",
        "summary": "半導体 (SMH) に資金流入圧力proxyが集中しています。",
        "leaders": [
            {
                "ticker": "SMH",
                "label": "半導体",
                "leadership_score": 1.2,
                "flow_pressure_z": 0.8,
                "relative_return_20d": 2.0,
                "relative_return_60d": 4.0,
                "trend_above_ma50": True,
                "level": "green",
            }
        ],
        "laggards": [],
        "source": "test",
    }


def _patch_new_market_layers(monkeypatch):
    monkeypatch.setattr(service, "get_stock_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        service,
        "_build_volatility_sentiment_context",
        lambda *args, **kwargs: {
            "volatility_regime": {"regime": "normal", "warnings": []},
            "sentiment": {"score": 50, "quality_warnings": []},
            "vix_sq_alert": {"status": "available", "quality_warnings": []},
            "short_horizon_forecast": {
                "status": "validated",
                "quality_warnings": [],
            },
            "composite_sentiment": {
                "status": "confirmed",
                "quality_warnings": [],
            },
        },
    )
    monkeypatch.setattr(
        service,
        "build_sector_flow_context",
        lambda market_type="US": _sector_flow_payload(),
    )
    monkeypatch.setattr(
        service,
        "build_credit_stress_monitor",
        lambda market_type: _credit_stress_payload(),
    )
    monkeypatch.setattr(
        service,
        "build_sector_flow_monitor",
        lambda market_type: _flow_monitor_payload(),
    )
    monkeypatch.setattr(
        service,
        "build_japan_conditions_context",
        lambda market_data, sector_flow: _japan_conditions_payload(),
    )
    monkeypatch.setattr(
        service,
        "build_cross_market_context",
        lambda sector_flow: {
            "stance": "US flow leadership remains dominant; Japan is supplemental.",
            "relative_flow_score": -20.0,
        },
    )
    monkeypatch.setattr(
        service,
        "build_trend_ranking_context",
        lambda market_type, **kwargs: {
            "items": [
                {
                    "rank": 1,
                    "theme": "AI",
                    "parent_sector": "情報技術",
                    "proxy_ticker": "SMH",
                    "option_asymmetry": "upside_squeeze_candidate"
                    if kwargs.get("include_options")
                    else "unavailable",
                    "total_score": 55.0,
                    "rank_points": 10,
                }
            ],
            "summary": "首位は AI。",
            "quality_warnings": [],
        },
    )
    monkeypatch.setattr(
        service,
        "build_opportunity_themes",
        lambda trend_ranking, market_distortions=None: {
            "items": [
                {
                    "theme": "AI",
                    "label": "投資妙味/上方向非対称",
                    "opportunity_score": 60,
                    "reason": "統合順位 1位",
                }
            ],
            "summary": "注目候補は AI。",
        },
    )
    monkeypatch.setattr(
        service,
        "build_market_strategy_context",
        lambda market_type, **kwargs: {
            "important_levels": {"items": [], "summary": "levels"},
            "market_timeframes": {
                "items": [
                    {
                        "key": "current",
                        "label": "現在時点",
                        "direction_label": "上昇相場",
                        "market_tone": "強気",
                        "score": 0.5,
                    }
                ],
                "summary": "現在時点: 上昇相場",
            },
            "strategy_regime": {
                "key": "trend_following",
                "label": "順張り",
                "risk_budget": "30-70%",
            },
            "market_driver_monitor": {"items": [], "summary": "drivers"},
        },
    )
    monkeypatch.setattr(
        service,
        "classify_ibd_market_regime",
        lambda spy_df, ndx_df: type(
            "Regime",
            (),
            {
                "to_dict": lambda self: {
                    "status_key": "confirmed_uptrend",
                    "label": "Confirmed Uptrend",
                    "score": 0.9,
                    "weight": 2.0,
                    "exposure_level": "60-100%",
                    "rationale": "test regime",
                    "quality_warnings": [],
                }
            },
        )(),
    )
    monkeypatch.setattr(
        service,
        "detect_market_distortions",
        lambda market_type, max_themes=30, top_n=5: {
            "bullish": [
                {"theme": "AI", "tickers": ["NVDA", "MSFT"], "distortion_score": 0.3}
            ],
            "bearish": [
                {
                    "theme": "Crowded",
                    "tickers": ["TSLA", "PLTR"],
                    "distortion_score": -0.4,
                }
            ],
            "quality_warnings": [],
        },
    )


def test_data_status_replaces_previous_feature_status():
    previous = DataResult(
        name="market_details_medium",
        is_partial=True,
        error="old failure",
        cache_status="failed",
    )
    current = DataResult(
        name="market_details_medium",
        is_partial=False,
        error="",
        cache_status="live",
    )

    statuses = service._replace_data_status([previous], current)

    assert statuses == [current]


def test_build_market_context_collects_monitoring_inputs(
    monkeypatch, mock_finnhub_client
):
    _patch_new_market_layers(monkeypatch)
    monkeypatch.setattr(service, "_save_context_cache", lambda context, kind: None)
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
        "get_major_indices_option_status",
        lambda market_type: {
            "items": [{"ticker": "SPY", "pcr": {"volume_pcr": 0.9}}],
            "status": "available",
            "failed_tickers": [],
            "error_message": "",
        },
    )
    monkeypatch.setattr(
        service,
        "evaluate_market_environment",
        lambda market_type, options, **kwargs: {
            "status": "Neutral",
            "score": 0.1,
            "signals": [{"name": "Trend", "score": 0.2, "rationale": "Stable"}],
        },
    )
    monkeypatch.setattr(
        service,
        "analyze_market_structure",
        lambda ticker, option_analysis=None, **kwargs: {
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
    assert context.evaluation["status"] == "🟢 強気 (Bullish)"
    assert context.ibd_regime["label"] == "Confirmed Uptrend"
    assert context.market_distortions["bullish"][0]["theme"] == "AI"
    assert context.monitor["distribution_spy"]["count"] == 2
    assert context.sector_flow["markets"]["US"]["leaders"][0]["theme"] == "情報技術"
    assert context.credit_stress["status"] == "equity_adjustment"
    assert context.flow_monitor["leaders"][0]["ticker"] == "SMH"
    assert context.flow_alignment["etf_leader"]["ticker"] == "SMH"
    assert context.detail_stages["theme_flow"]["status"] == "live"
    assert context.detail_stages["volatility_sentiment"]["status"] == "live", (
        context.errors
    )
    assert context.detail_stages["credit_distortion"]["status"] == "live"
    assert context.japan_conditions == {}
    assert context.cross_market == {}
    assert context.trend_ranking["items"][0]["theme"] == "AI"
    assert context.opportunity_themes["items"][0]["theme"] == "AI"
    assert context.strategy_regime["label"] == "順張り"
    assert "Market environment" in service.format_market_context_for_ai(context)
    assert "NVDA, MSFT" in service.format_market_context_for_ai(context)
    assert "ETF proxy / sector-flow role split" in service.format_market_context_for_ai(
        context
    )
    assert "Integrated trend ranking" in service.format_market_context_for_ai(context)
    assert "Strategy regime" in service.format_market_context_for_ai(context)
    assert "Nikkei upside six conditions" not in service.format_market_context_for_ai(
        context
    )
    assert "[Data provenance]" in service.format_market_context_for_ai(context)
    assert "kind=proxy" in service.format_market_context_for_ai(context)


def test_market_ai_prompt_includes_option_term_structure():
    context = MarketContext(
        market_type="US",
        options=OptionContext(
            horizons=[
                {
                    "key": "one_week",
                    "label": "1週間",
                    "iv": 0.22,
                    "expected_move_pct": 0.018,
                    "pcr_volume": 1.2,
                    "skew": 0.04,
                    "nearby_net_gex": -1_000_000,
                }
            ],
            term_structure={"summary": "1W IV=22.0% / 1M IV=25.0%"},
        ),
    )

    prompt = service.format_market_context_for_ai(context)

    assert "[Options term structure]" in prompt
    assert "1sigma_move" in prompt
    assert "nearby_gex=negative" in prompt


def test_build_market_context_keeps_partial_data_when_options_fail(monkeypatch):
    _patch_new_market_layers(monkeypatch)
    monkeypatch.setattr(service, "_save_context_cache", lambda context, kind: None)
    monkeypatch.setattr(service, "get_market_indices", lambda market_type: {"SPY": {}})
    monkeypatch.setattr(service, "get_market_config", lambda market_type: {})
    monkeypatch.setattr(
        service,
        "get_major_indices_option_status",
        lambda market_type: (_ for _ in ()).throw(RuntimeError("rate limited")),
    )
    monkeypatch.setattr(
        service,
        "evaluate_market_environment",
        lambda market_type, options, **kwargs: {
            "status": "Neutral",
            "score": 0,
            "signals": [],
        },
    )
    monkeypatch.setattr(
        service,
        "analyze_market_structure",
        lambda ticker, option_analysis=None, **kwargs: {},
    )
    monkeypatch.setattr(service, "get_momentum_themes", lambda market_type: {})
    monkeypatch.setattr(
        service, "build_market_monitor_context", lambda options: _monitor_payload()
    )

    context = service.build_market_context("US")

    assert context.market_data == {"SPY": {}}
    assert context.options.items == []
    assert context.options.status == "failed"
    assert "Option analysis failed" in context.options.error_message


def test_market_summary_context_does_not_fetch_options(monkeypatch):
    monkeypatch.setattr(service, "_save_context_cache", lambda context, kind: None)
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
        "get_major_indices_option_status",
        lambda market_type: (_ for _ in ()).throw(AssertionError("should not fetch")),
    )

    context = service.build_market_summary_context("US")

    assert context.market_data["S&P 500"]["ticker"] == "SPY"
    assert context.options.items == []
    assert context.source == "live_summary"
    assert context.provenance[0].kind.value == "direct"


def test_market_monitor_does_not_invent_missing_yield_or_valuation(monkeypatch):
    monkeypatch.setattr(
        service, "get_stock_data", lambda ticker, period: pd.DataFrame()
    )
    monkeypatch.setattr(service, "get_valuation_metrics", lambda ticker: {})

    monitor = service.build_market_monitor_context([])

    assert monitor["yield_spread"]["available"] is False
    assert monitor["yield_spread"]["yield_10y"] is None
    assert monitor["yield_spread"]["spreads"] == {}
    assert service._extract_spy_pcr([]) is None
    assert service._extract_pe({}) is None
    assert "10Y=unavailable" in service.format_market_context_for_ai(
        MarketContext(market_type="US", monitor=monitor)
    )


def test_market_context_cache_preserves_stale_metadata(monkeypatch, tmp_path):
    store = PersistentJsonCache(tmp_path, service.MARKET_CONTEXT_CACHE_NAMESPACE)
    monkeypatch.setattr(service, "_market_context_cache", lambda: store)
    context = MarketContext(
        market_type="US",
        market_data={"S&P 500": {"ticker": "SPY", "price": 500, "change": 1}},
        market_config={"indices": {"S&P 500": "SPY"}},
        source="live_summary",
        fetched_at="2026-01-01T00:00:00+00:00",
        data_status=[DataResult(name="market_indices", source="market_data")],
    )

    service._save_context_cache(context, "summary")
    loaded = service._load_context_cache(
        "US",
        "summary",
        max_age_seconds=86_400_000,
        fresh_seconds=1,
    )

    assert loaded is not None
    assert loaded.cache_status == "stale_cache"
    assert loaded.is_stale is True
    assert loaded.data_status[0].cache_status == "stale_cache"
    assert any(item.kind.value == "stale_cache" for item in loaded.provenance)


def test_market_context_round_trip_preserves_forecast_and_composite_layers():
    context = MarketContext(
        market_type="US",
        short_horizon_forecast={
            "status": "research_only",
            "targets": {"SPY": {"horizons": {"5d": {"probability_up": 0.55}}}},
        },
        composite_sentiment={
            "status": "confirmed",
            "targets": {"SPY": {"state": "hidden_tail_hedging"}},
        },
    )

    restored = MarketContext.from_mapping(context.to_dict())

    assert restored.short_horizon_forecast == context.short_horizon_forecast
    assert restored.composite_sentiment == context.composite_sentiment


def test_market_details_reuses_supplied_context(monkeypatch):
    _patch_new_market_layers(monkeypatch)
    base = MarketContext(
        market_type="US",
        market_data={"S&P 500": {"ticker": "SPY", "price": 500, "change": 1}},
        market_config={"indices": {"S&P 500": "SPY"}},
        options=OptionContext(items=[{"ticker": "SPY", "pcr": {"volume_pcr": 0.9}}]),
    )
    monkeypatch.setattr(service, "_save_context_cache", lambda context, kind: None)
    monkeypatch.setattr(
        service,
        "get_market_indices",
        lambda market_type: (_ for _ in ()).throw(AssertionError("should reuse data")),
    )
    monkeypatch.setattr(
        service,
        "get_market_config",
        lambda market_type: (_ for _ in ()).throw(
            AssertionError("should reuse config")
        ),
    )
    monkeypatch.setattr(
        service,
        "evaluate_market_environment",
        lambda market_type, options, **kwargs: {
            "status": "Neutral",
            "score": 0,
            "signals": [],
        },
    )
    monkeypatch.setattr(
        service,
        "analyze_market_structure",
        lambda ticker, option_analysis=None, **kwargs: {},
    )
    monkeypatch.setattr(service, "get_momentum_themes", lambda market_type: {})
    monkeypatch.setattr(
        service, "build_market_monitor_context", lambda options: _monitor_payload()
    )

    context = service.build_market_details_context("US", base.to_dict())

    assert context.market_data == base.market_data
    assert context.options.items == base.options.items
    assert context.monitor["distribution_spy"]["count"] == 2
    assert context.cross_market == {}


def test_market_detail_stages_can_update_sequentially(monkeypatch, mock_finnhub_client):
    _patch_new_market_layers(monkeypatch)
    base = MarketContext(
        market_type="US",
        market_data={"S&P 500": {"ticker": "SPY", "price": 500, "change": 1}},
        market_config={"indices": {"S&P 500": "SPY"}},
        options=OptionContext(items=[{"ticker": "SPY", "pcr": {"volume_pcr": 0.9}}]),
    )
    monkeypatch.setattr(service, "_save_context_cache", lambda context, kind: None)
    monkeypatch.setattr(
        service,
        "evaluate_market_environment",
        lambda market_type, options, **kwargs: {
            "status": "Neutral",
            "score": 0,
            "signals": [],
        },
    )
    monkeypatch.setattr(
        service,
        "analyze_market_structure",
        lambda ticker, option_analysis=None, **kwargs: {},
    )
    monkeypatch.setattr(service, "get_momentum_themes", lambda market_type: {})
    monkeypatch.setattr(
        service, "build_market_monitor_context", lambda options: _monitor_payload()
    )

    theme_flow = service.build_market_theme_flow_context("US", base.to_dict())
    volatility = service.build_market_volatility_sentiment_context(
        "US", theme_flow.to_dict()
    )
    high = service.build_market_high_context("US", volatility.to_dict())

    assert theme_flow.detail_stages["core"]["status"] == "pending"
    assert theme_flow.detail_stages["theme_flow"]["status"] == "live"
    assert theme_flow.detail_stages["volatility_sentiment"]["status"] == "pending"
    assert volatility.detail_stages["theme_flow"]["status"] == "live"
    assert volatility.detail_stages["volatility_sentiment"]["status"] == "live", (
        volatility.errors
    )
    assert high.detail_stages["credit_distortion"]["status"] == "live"
    assert high.market_distortions["bullish"][0]["tickers"] == ["NVDA", "MSFT"]


def test_market_stage_task_timeout_records_partial_result():
    errors: list[str] = []
    release_event = threading.Event()

    def slow_task():
        release_event.wait(timeout=1)
        return {"late": True}

    started = time.perf_counter()
    results = service._run_stage_tasks(
        {
            "fast": lambda: {"ok": True},
            "slow": slow_task,
        },
        errors,
        stage_name="test_stage",
        max_workers=2,
        task_timeout_seconds=0.01,
        total_timeout_seconds=0.05,
    )
    release_event.set()

    assert time.perf_counter() - started < 0.15
    assert results["fast"].value == {"ok": True}
    assert results["fast"].status == "ok"
    assert results["slow"].status == "timed_out"
    assert results["slow"].timed_out is True
    assert "test_stage.slow timed out" in results["slow"].error
    assert any("test_stage.slow timed out" in error for error in errors)


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
        sector_flow=_sector_flow_payload(),
        credit_stress=_credit_stress_payload(),
        flow_monitor=_flow_monitor_payload(),
        flow_alignment={
            "summary": "ETF proxy is risk-on; sector flow points to Technology.",
            "etf_role": "市場全体の確認",
            "sector_role": "具体候補",
        },
        trend_ranking={"items": [{"rank": 1, "theme": "AI", "total_score": 50}]},
        opportunity_themes={
            "items": [
                {
                    "theme": "AI",
                    "label": "上昇候補",
                    "opportunity_score": 55,
                    "reason": "統合順位 1位",
                }
            ]
        },
        strategy_regime={
            "key": "trend_following",
            "label": "順張り",
            "risk_budget": "30-70%",
        },
        market_timeframes={
            "items": [
                {
                    "key": "current",
                    "label": "現在時点",
                    "direction_label": "上昇相場",
                    "market_tone": "強気",
                    "score": 0.5,
                    "confidence": "中",
                }
            ]
        },
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
    monkeypatch.setattr(
        market_analyst_service,
        "get_ranked_themes",
        lambda period: (_ for _ in ()).throw(AssertionError("should reuse momentum")),
    )
    monkeypatch.setattr(
        market_analyst_service,
        "get_stock_data",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should reuse market context")
        ),
    )
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
    assert "Credit stress velocity" in captured["advanced"]
    assert "Leadership flow-pressure proxy" in captured["advanced"]
    assert "Sector/theme flow" in captured["advanced"]
    assert "ETF proxy / sector-flow role split" in captured["advanced"]
    assert "Integrated trend ranking" in captured["advanced"]
    assert "Strategy regime" in captured["advanced"]
    assert "Nikkei upside six conditions" not in captured["advanced"]


def test_market_ai_report_reports_gemini_unavailable():
    result = market_analyst_service.generate_market_analysis_report(
        "US", gemini_configured=False
    )

    assert result == "Gemini APIが利用できません。APIキーを設定してください。"


def test_theme_flow_uses_provided_only_option_policy(monkeypatch):
    _patch_new_market_layers(monkeypatch)
    base = MarketContext(market_type="US", market_data={"S&P 500": {"price": 500}})
    calls = {}
    monkeypatch.setattr(service, "_save_context_cache", lambda context, kind: None)

    def microstructure(ticker, option_analysis=None, **kwargs):
        calls["microstructure"] = (option_analysis, kwargs)
        return {}

    def evaluation(market_type, options, **kwargs):
        calls["evaluation"] = kwargs
        return {"status": "Neutral", "score": 0, "signals": []}

    monkeypatch.setattr(service, "analyze_market_structure", microstructure)
    monkeypatch.setattr(service, "evaluate_market_environment", evaluation)
    monkeypatch.setattr(service, "get_momentum_themes", lambda market_type: {})
    monkeypatch.setattr(
        service, "build_market_monitor_context", lambda options: _monitor_payload()
    )

    service.build_market_theme_flow_context("US", base)

    assert calls["microstructure"][0] == {}
    assert calls["microstructure"][1]["allow_option_fetch"] is False
    assert calls["evaluation"]["allow_microstructure_fetch"] is False
