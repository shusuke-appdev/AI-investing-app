from src.services import trend_ranking_service as service


def test_trend_ranking_reflects_marketdata_option_asymmetry(monkeypatch):
    def fake_ranked(periods, market_type):
        raw = {
            "1週間": {"AI半導体": 4.0, "石油・ガス": 1.0},
            "1ヶ月": {"AI半導体": 8.0, "石油・ガス": 2.0},
            "6ヶ月": {"AI半導体": 20.0, "石油・ガス": 3.0},
        }
        return {
            period: [
                {"theme": theme, "performance": performance}
                for theme, performance in raw[period].items()
            ]
            for period in periods
        }

    monkeypatch.setattr(service, "get_ranked_theme_periods", fake_ranked)
    monkeypatch.setattr(
        service,
        "get_themes",
        lambda market_type: {
            "AI半導体": ["NVDA", "AMD"],
            "石油・ガス": ["XOM", "CVX"],
        },
    )
    monkeypatch.setattr(
        service,
        "analyze_option_sentiment",
        lambda ticker, allow_marketdata=True: {
            "source": "marketdata.app",
            "data_quality": "available",
            "data_as_of": "2026-06-16T00:00:00+00:00",
            "pcr": {"volume_pcr": 0.5},
            "gex": {"nearby_net_gex": -10_000_000},
            "skew": 0.0,
            "quality_warnings": [],
        },
    )

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
    )

    assert result["items"][0]["theme"] == "AI半導体"
    assert result["items"][0]["option_asymmetry"] == "upside_squeeze_candidate"
    assert result["items"][0]["option_source"] == "marketdata.app"
    assert result["items"][0]["rank_points"] == 10


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
