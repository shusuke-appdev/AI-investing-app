from src.provider_result import FetchResult
from src.services import trend_ranking_service as service


def test_trend_ranking_reflects_marketdata_option_asymmetry(monkeypatch):
    option_calls = []

    monkeypatch.setattr(
        service,
        "get_comprehensive_theme_ranking_result",
        lambda market_type: FetchResult(
            data={
                "market": market_type,
                "status": "available",
                "items": [
                    {
                        "theme": "AI半導体",
                        "market": market_type,
                        "total_score": 50.0,
                        "rank_1w": 1,
                        "rank_1m": 1,
                        "rank_6m": 1,
                        "rank_acceleration": 0,
                        "performance_1w": 4.0,
                        "performance_1m": 8.0,
                        "performance_6m": 20.0,
                        "representative_tickers": ["NVDA", "AMD"],
                        "proxy_ticker": "SMH",
                        "option_proxy_ticker": "SMH",
                        "parent_sector": "情報技術",
                        "data_quality": "available",
                    },
                    {
                        "theme": "石油・ガス",
                        "market": market_type,
                        "total_score": 10.0,
                        "rank_1w": 2,
                        "rank_1m": 2,
                        "rank_6m": 2,
                        "rank_acceleration": 0,
                        "performance_1w": 1.0,
                        "performance_1m": 2.0,
                        "performance_6m": 3.0,
                        "representative_tickers": ["XOM", "CVX"],
                        "parent_sector": "エネルギー",
                        "data_quality": "available",
                    },
                ],
                "quality_warnings": [],
                "fetched_at": "2026-06-16T00:00:00+00:00",
            },
            source="test",
            status="available",
        ),
    )

    def fake_option_sentiment(ticker, *, allow_marketdata=True, cache_only=False):
        option_calls.append((ticker, allow_marketdata, cache_only))
        return {
            "source": "marketdata.app",
            "data_quality": "available",
            "data_as_of": "2026-06-16T00:00:00+00:00",
            "pcr": {"volume_pcr": 0.5},
            "gex": {"nearby_net_gex": -10_000_000},
            "skew": 0.0,
            "quality_warnings": [],
        }

    monkeypatch.setattr(service, "analyze_option_sentiment", fake_option_sentiment)

    result = service.build_trend_ranking_context(
        "US",
        sector_flow={
            "markets": {
                "US": {
                    "leaders": [
                        {
                            "theme": "AI半導体",
                            "flow_score": 40,
                            "participation": 0.8,
                        }
                    ]
                }
            }
        },
        distortions={
            "bullish": [
                {
                    "theme": "AI半導体",
                    "distortion_score": 0.3,
                    "classification": "bullish_distortion",
                }
            ]
        },
        include_options=True,
        option_cache_only=True,
    )

    assert result["items"][0]["theme"] == "AI半導体"
    assert result["items"][0]["option_asymmetry"] == "two_sided_vol_expansion"
    assert result["items"][0]["option_score"] == 4.0
    assert result["items"][0]["option_source"] == "marketdata.app"
    assert result["items"][0]["rank_points"] == 10
    assert result["items"][0]["rank_1w"] == 1
    assert result["items"][0]["rank_1m"] == 1
    assert result["items"][0]["rank_6m"] == 1
    assert result["items"][0]["rank_acceleration"] == 0
    assert result["option_mode"] == "cache_only"
    assert option_calls
    assert all(cache_only for _, _, cache_only in option_calls)


def test_theme_direction_requires_direct_skew_and_reliable_gamma():
    base = {
        "source": "marketdata.app",
        "provider_active": True,
        "complete_status": "complete",
        "gamma_coverage": 1.0,
        "is_stale": False,
        "gex": {"nearby_net_gex": -10_000_000},
        "pcr": {"volume_pcr": 1.0},
    }
    direct = {
        **base,
        "skew_detail": {
            "value": 0.08,
            "method": "delta_25_direct",
            "status": "direct",
            "liquidity_status": "ok",
        },
    }
    proxy = {
        **base,
        "skew_detail": {
            "value": 0.08,
            "method": "moneyness_10pct_proxy",
            "status": "proxy",
            "liquidity_status": "thin",
        },
    }

    assert (
        service._option_payload("SMH", direct)["option_asymmetry"]
        == "downside_vol_expansion"
    )
    assert service._option_payload("SMH", direct)["option_score"] == -12.0
    assert (
        service._option_payload("SMH", proxy)["option_asymmetry"]
        == "two_sided_vol_expansion"
    )
    assert service._option_payload("SMH", proxy)["option_score"] == 0.0

    positive_gex_proxy = {
        **proxy,
        "gex": {"nearby_net_gex": 10_000_000},
    }
    assert (
        service._option_payload("SMH", positive_gex_proxy)["option_asymmetry"]
        == "pinning"
    )
    assert service._option_payload("SMH", positive_gex_proxy)["option_score"] == 0.0


def test_opportunity_themes_use_ranking_and_option_asymmetry():
    result = service.build_opportunity_themes(
        {
            "items": [
                {
                    "theme": "AI半導体",
                    "parent_sector": "情報技術",
                    "rank": 1,
                    "total_score": 45,
                    "option_score": 12,
                    "option_asymmetry": "upside_squeeze_candidate",
                    "representative_tickers": ["NVDA", "AMD"],
                    "proxy_ticker": "SMH",
                    "option_proxy_ticker": "SMH",
                }
            ]
        }
    )

    assert result["items"][0]["theme"] == "AI半導体"
    assert "非対称" in result["items"][0]["label"]
    assert result["items"][0]["proxy_ticker"] == "SMH"
    assert result["items"][0]["option_proxy_ticker"] == "SMH"


def test_opportunity_themes_supplement_to_multiple_observation_candidates():
    result = service.build_opportunity_themes(
        {
            "items": [
                {
                    "theme": "AI半導体",
                    "parent_sector": "情報技術",
                    "rank": 1,
                    "total_score": 45,
                    "option_score": 0,
                    "option_asymmetry": "unavailable",
                    "representative_tickers": ["NVDA"],
                    "proxy_ticker": "SMH",
                    "option_proxy_ticker": "SMH",
                },
                {
                    "theme": "原子力",
                    "parent_sector": "公益",
                    "rank": 2,
                    "total_score": 12,
                    "option_score": 0,
                    "option_asymmetry": "unavailable",
                    "representative_tickers": ["CEG"],
                    "proxy_ticker": "NLR",
                    "option_proxy_ticker": "XLU",
                },
                {
                    "theme": "防衛",
                    "parent_sector": "資本財",
                    "rank": 3,
                    "total_score": 10,
                    "option_score": 0,
                    "option_asymmetry": "unavailable",
                    "representative_tickers": ["LMT"],
                    "proxy_ticker": "ITA",
                    "option_proxy_ticker": "ITA",
                },
            ]
        }
    )

    assert [item["theme"] for item in result["items"]] == [
        "AI半導体",
        "原子力",
        "防衛",
    ]
    assert result["items"][1]["label"] == "観察"
