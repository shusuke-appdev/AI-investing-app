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
        detail_stages={
            "low": {
                "key": "low",
                "label": "低: サマリー/キャッシュ",
                "difficulty": "低",
                "status": "cache",
                "status_label": "キャッシュ",
                "cache_status": "persistent_cache",
                "fetched_at": "2026-01-01T00:00:00+00:00",
                "summary": "cached",
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
    assert display.market_signals[0].category == "bullish"
    assert display.momentum_data[0].themes[0].performance_str == "+3.2%"
    assert display.bullish_distortions[0].tickers == ["NVDA", "MSFT"]
    assert display.sector_flow_groups[0].leaders[0].flow_score_str == "+50.0"
    assert display.flow_alignment.alignment_label == "整合"
    assert display.detail_stages[0].status_label == "キャッシュ"
