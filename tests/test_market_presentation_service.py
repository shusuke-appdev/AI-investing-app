from src.services.analysis_context import MarketContext, OptionContext
from src.services.market_presentation_service import build_market_display_context


def test_market_display_context_formats_market_context_for_reflex_state():
    context = MarketContext(
        market_type="US",
        market_data={
            "S&P 500": {"ticker": "SPY", "price": 5300.4, "change": 0.54},
            "Technology": {"ticker": "XLK", "price": 240.12, "change": 1.2},
            "Bitcoin": {"ticker": "BTC-USD", "price": 68000.0, "change": -2.4},
        },
        market_config={
            "indices": {"S&P 500": "SPY"},
            "sectors": {"Technology": "XLK"},
            "crypto": {"Bitcoin": "BTC-USD"},
        },
        options=OptionContext(
            items=[
                {
                    "ticker": "SPY",
                    "current_price": 530.12,
                    "pcr": {"volume_pcr": 0.83},
                    "gex": {"nearby_net_gex": 12_000_000},
                    "iv": 0.18,
                    "max_pain": 525,
                    "data_quality": "partial",
                    "provider_active": True,
                    "gamma_coverage": 1.0,
                    "complete_status": "complete",
                }
            ]
        ),
        evaluation={
            "signals": [{"name": "Trend", "score": 0.5, "weight": 1, "rationale": "Up"}]
        },
        ibd_regime={"status_key": "confirmed_uptrend", "label": "Confirmed"},
        momentum={"1週間": [{"theme": "AI", "performance": 3.25}]},
        market_distortions={
            "bullish": [
                {
                    "theme": "AI",
                    "tickers": ["NVDA", "MSFT"],
                    "distortion_score": 0.35,
                    "rationale": "test",
                }
            ],
            "bearish": [],
        },
        sector_flow={
            "summary": "US flow",
            "markets": {
                "US": {
                    "leaders": [
                        {
                            "theme": "Technology",
                            "flow_score": 50,
                            "confidence": "高",
                            "continuation": "中",
                            "action": "乗る候補",
                        }
                    ]
                }
            },
        },
        flow_alignment={
            "summary": "ETF proxy confirms the broad tape.",
            "alignment_label": "整合",
            "etf_role": "市場全体の確認",
            "sector_role": "具体候補",
        },
        strategy_regime={
            "key": "trend_following",
            "label": "順張り",
            "risk_budget": "30-70%",
            "rationale": "test",
        },
        market_timeframes={
            "items": [
                {
                    "key": "current",
                    "label": "現在時点",
                    "score": 0.5,
                    "market_tone": "強気",
                    "direction_label": "上昇相場",
                    "confidence": "中",
                }
            ]
        },
        important_levels={
            "summary": "SPY breakout",
            "items": [
                {
                    "label": "S&P 500",
                    "ticker": "SPY",
                    "close": 530.12,
                    "support": 510.0,
                    "resistance": 535.0,
                    "behavior": "breakout",
                    "behavior_label": "突破",
                    "data_quality": "ok",
                }
            ],
        },
        trend_ranking={
            "summary": "首位は AI半導体。",
            "items": [
                {
                    "rank": rank,
                    "theme": f"AI半導体{rank}",
                    "parent_sector": "情報技術",
                    "proxy_ticker": "SMH",
                    "option_proxy_ticker": "SMH",
                    "total_score": 50.0 - rank,
                    "rank_points": 10,
                    "option_asymmetry": "upside_squeeze_candidate",
                    "representative_tickers": ["NVDA"],
                }
                for rank in range(1, 8)
            ],
        },
        opportunity_themes={
            "summary": "注目候補は AI半導体。",
            "items": [
                {
                    "theme": "AI半導体",
                    "label": "投資妙味/上方向非対称",
                    "opportunity_score": 60,
                    "rank": 1,
                }
            ],
        },
        detail_stages={
            "core": {
                "key": "core",
                "label": "Core: 市場概要/キャッシュ",
                "difficulty": "低",
                "status": "cache",
                "status_label": "キャッシュ",
                "cache_status": "persistent_cache",
                "fetched_at": "2026-01-01T00:00:00+00:00",
                "summary": "cached",
                "target": "市場概要とキャッシュ復元",
                "error_message": "",
                "quality_warnings": [],
            }
        },
    )

    display = build_market_display_context(context)

    assert display.indices_data == [
        {"name": "S&P 500", "price": "5,300", "change": 0.5}
    ]
    assert display.sectors_data[0]["name"] == "Technology"
    assert display.others_data[0]["price"] == "$68.0K"
    assert display.option_analysis[0].net_gex_str == "+12M"
    assert display.option_analysis[0].complete_status_label == "完全取得"
    assert display.option_analysis[0].gamma_coverage_str == "100%"
    assert display.option_analysis[0].provider_active is True
    assert display.market_signals[0].category == "bullish"
    assert display.momentum_data[0].themes[0].performance_str == "+3.2%"
    assert display.bullish_distortions[0].tickers == ["NVDA", "MSFT"]
    assert display.sector_flow_groups[0].leaders[0].flow_score_str == "+50.0"
    assert display.flow_alignment.alignment_label == "整合"
    assert display.strategy_regime.label == "順張り"
    assert display.market_timeframes[0].direction_label == "上昇相場"
    assert display.important_levels[0].behavior_label == "突破"
    assert len(display.trend_ranking_items) == 5
    assert display.trend_ranking_items[0].option_asymmetry == "upside_squeeze_candidate"
    assert display.trend_ranking_items[-1].rank == 5
    assert display.opportunity_theme_items[0].theme == "AI半導体"
    assert display.detail_stages[0].status_label == "キャッシュ"
    assert display.detail_stages[0].target == "市場概要とキャッシュ復元"


def test_market_display_context_uses_configured_market_order():
    context = MarketContext(
        market_type="US",
        market_data={
            "Bitcoin": {"ticker": "BTC-USD", "price": 68000.0, "change": 2.0},
            "Sensex": {"ticker": "^BSESN", "price": 75000.0, "change": 0.1},
            "S&P 500": {"ticker": "^GSPC", "price": 5300.0, "change": 0.2},
            "Ethereum": {"ticker": "ETH-USD", "price": 3500.0, "change": 3.0},
            "Dow 30": {"ticker": "^DJI", "price": 39000.0, "change": -0.1},
            "Gold": {"ticker": "GC=F", "price": 2300.0, "change": 0.4},
            "USD/JPY": {"ticker": "JPY=X", "price": 155.0, "change": 0.2},
        },
        market_config={
            "indices": {
                "S&P 500": "^GSPC",
                "Dow 30": "^DJI",
                "Sensex": "^BSESN",
            },
            "sectors": {},
            "commodities": {"Gold": "GC=F"},
            "forex": {"USD/JPY": "JPY=X"},
            "crypto": {"Ethereum": "ETH-USD", "Bitcoin": "BTC-USD"},
        },
    )

    display = build_market_display_context(context)

    assert [item["name"] for item in display.indices_data] == [
        "S&P 500",
        "Dow 30",
        "Sensex",
    ]
    assert [item["name"] for item in display.others_data] == [
        "Gold",
        "USD/JPY",
        "Ethereum",
        "Bitcoin",
    ]
