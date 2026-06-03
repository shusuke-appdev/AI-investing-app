from src.stock_analyst import _format_sector_theme_context, _format_trend_follow_context


def test_format_trend_follow_context_marks_diagnostics_as_context_only():
    context = {
        "trend_follow_diagnostics": {
            "rating_display": "Fragile",
            "current_state_display": "50D MA is above 200D MA.",
            "strategy_total_return_display": "+12.30%",
            "buy_hold_total_return_display": "+20.00%",
            "oos_alpha_display": "-4.20%",
            "top5_removed_display": "-1.00%",
            "random_percentile_display": "42.00%",
            "strategy_max_drawdown_display": "-18.00%",
            "strategy_tuw_display": "140 days",
            "warnings": ["OOS return did not beat Buy & Hold."],
        }
    }

    text = _format_trend_follow_context(context)

    assert "diagnostic only" in text
    assert "Fragile" in text
    assert "OOS return did not beat Buy & Hold." in text


def test_format_trend_follow_context_handles_missing_data():
    assert _format_trend_follow_context({}) == "Trend-Follow Diagnostics: unavailable."


def test_format_sector_theme_context_includes_advantage_flags():
    text = _format_sector_theme_context(
        {
            "sector_theme_context": {
                "sector": "Technology",
                "themes": ["AI"],
                "fundamental_advantage": True,
                "flow_advantage": True,
                "combined_rating": "high",
                "rationale": "Both advantages exist.",
                "theme_diagnostics": [
                    {
                        "theme": "AI",
                        "fundamental_score": 0.75,
                        "flow_score": 0.7,
                        "classification": "fundamental_and_flow_aligned",
                    }
                ],
            }
        }
    )

    assert "Sector/Theme Context" in text
    assert "Combined Rating: high" in text
    assert "fundamental=True" in text or "Stock Fundamental Advantage: True" in text
