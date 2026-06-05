from src.persistent_cache import PersistentJsonCache
from src.services import market_analyst_service
from src.services import market_dashboard_service as service
from src.services.analysis_context import DataResult, MarketContext, OptionContext


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
        "summary": "米国: 情報技術(+50.0) / 日本: 半導体製造装置(+30.0)",
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
            "JP": {
                "leaders": [
                    {
                        "theme": "半導体製造装置",
                        "flow_score": 30.0,
                        "confidence": "中",
                        "continuation": "中",
                        "action": "押し目待ち",
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
    monkeypatch.setattr(service, "build_sector_flow_context", _sector_flow_payload)
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


def test_build_market_context_collects_monitoring_inputs(monkeypatch):
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
    assert context.evaluation["status"] == "🟢 強気 (Bullish)"
    assert context.ibd_regime["label"] == "Confirmed Uptrend"
    assert context.market_distortions["bullish"][0]["theme"] == "AI"
    assert context.monitor["distribution_spy"]["count"] == 2
    assert context.sector_flow["markets"]["US"]["leaders"][0]["theme"] == "情報技術"
    assert context.credit_stress["status"] == "equity_adjustment"
    assert context.flow_monitor["leaders"][0]["ticker"] == "SMH"
    assert context.flow_alignment["etf_leader"]["ticker"] == "SMH"
    assert context.detail_stages["medium"]["status"] == "live"
    assert context.detail_stages["high"]["status"] == "live"
    assert context.japan_conditions["score_label"] == "中立"
    assert "Market environment" in service.format_market_context_for_ai(context)
    assert "NVDA, MSFT" in service.format_market_context_for_ai(context)
    assert "ETF proxy / sector-flow role split" in service.format_market_context_for_ai(
        context
    )
    assert "Nikkei upside six conditions" in service.format_market_context_for_ai(
        context
    )


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
        lambda market_type, options: {"status": "Neutral", "score": 0, "signals": []},
    )
    monkeypatch.setattr(service, "analyze_market_structure", lambda ticker: {})
    monkeypatch.setattr(service, "get_momentum_themes", lambda market_type: {})
    monkeypatch.setattr(
        service, "build_market_monitor_context", lambda options: _monitor_payload()
    )

    context = service.build_market_details_context("US", base.to_dict())

    assert context.market_data == base.market_data
    assert context.options.items == base.options.items
    assert context.monitor["distribution_spy"]["count"] == 2
    assert context.cross_market["relative_flow_score"] == -20.0


def test_market_detail_stages_can_update_sequentially(monkeypatch):
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
        lambda market_type, options: {"status": "Neutral", "score": 0, "signals": []},
    )
    monkeypatch.setattr(service, "analyze_market_structure", lambda ticker: {})
    monkeypatch.setattr(service, "get_momentum_themes", lambda market_type: {})
    monkeypatch.setattr(
        service, "build_market_monitor_context", lambda options: _monitor_payload()
    )

    medium = service.build_market_medium_context("US", base.to_dict())
    high = service.build_market_high_context("US", medium.to_dict())

    assert medium.detail_stages["low"]["status"] == "pending"
    assert medium.detail_stages["medium"]["status"] == "live"
    assert medium.detail_stages["high"]["status"] == "pending"
    assert high.detail_stages["medium"]["status"] == "live"
    assert high.detail_stages["high"]["status"] == "live"
    assert high.market_distortions["bullish"][0]["tickers"] == ["NVDA", "MSFT"]


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
        japan_conditions=_japan_conditions_payload(),
        cross_market={
            "stance": "US flow leadership remains dominant; Japan is supplemental.",
            "relative_flow_score": -20.0,
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
    assert "US primary / Japan supplemental sector flow" in captured["advanced"]
    assert "ETF proxy / sector-flow role split" in captured["advanced"]


def test_market_ai_report_reports_gemini_unavailable():
    result = market_analyst_service.generate_market_analysis_report(
        "US", gemini_configured=False
    )

    assert result == "Gemini APIが利用できません。APIキーを設定してください。"
