import pytest

from src.services.analysis_context import DataResult, MarketContext
from src.services.analysis_diagnostics import (
    assert_context_quality,
    assert_data_result_ok,
    assert_no_unexplained_partial_data,
)


def test_data_result_diagnostic_message_includes_market_context_fields():
    result = DataResult(
        name="news",
        source="finnhub",
        fetched_at="2026-05-27T00:00:00+00:00",
        is_partial=True,
        error="401 unauthorized",
        cache_status="failed",
    )

    with pytest.raises(AssertionError) as exc:
        assert_data_result_ok(
            result,
            context={
                "ticker": "AAPL",
                "provider": "finnhub",
                "quality_warnings": ["using fallback"],
            },
        )

    message = str(exc.value)
    assert "ticker=AAPL" in message
    assert "provider=finnhub" in message
    assert "cache_status=failed" in message
    assert "quality_warnings=['using fallback']" in message


def test_no_unexplained_partial_data_requires_error_or_warning():
    partial = DataResult(name="options", source="yfinance", is_partial=True)

    with pytest.raises(AssertionError) as exc:
        assert_no_unexplained_partial_data([partial], context={"ticker": "SPY"})

    assert "Unexplained partial data" in str(exc.value)
    assert "ticker=SPY" in str(exc.value)

    assert_no_unexplained_partial_data(
        [partial],
        quality_warnings=["yfinance missing Greeks"],
        context={"ticker": "SPY"},
    )


def test_context_quality_reports_partial_context():
    context = MarketContext(
        market_type="US",
        source="persistent_cache",
        fetched_at="2026-05-27T00:00:00+00:00",
        is_partial=True,
        quality_warnings=["using stale market context"],
        cache_status="stale_cache",
    )

    with pytest.raises(AssertionError) as exc:
        assert_context_quality(context)

    message = str(exc.value)
    assert "Context quality failed" in message
    assert "provider=persistent_cache" in message
    assert "cache_status=stale_cache" in message
