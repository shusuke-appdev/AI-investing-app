from src.services.analysis_context import MarketContext
from src.services.market_analyst_service import _format_theme_analysis_from_context


def test_market_ai_theme_format_uses_distinct_laggards():
    context = MarketContext(
        market_type="US",
        momentum={
            "短期": [
                {"theme": f"Theme {index}", "performance": float(10 - index)}
                for index in range(10)
            ]
        },
    )

    result = _format_theme_analysis_from_context(context)

    assert "Top5: Theme 0(+10.0%)" in result
    assert "Bottom5: Theme 5(+5.0%)" in result
    assert "Bottom5: Theme 0" not in result
