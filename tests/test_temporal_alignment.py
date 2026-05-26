import pandas as pd

from src.services.temporal_alignment import (
    DELTA_SECONDS_COLUMN,
    MATCHED_COLUMN,
    align_temporal_asof,
)


def test_temporal_alignment_matches_backward_with_tolerance():
    trades = pd.DataFrame(
        {
            "timestamp": ["2026-05-27 09:30:00", "2026-05-27 09:31:00"],
            "trade_price": [100.5, 101.5],
        }
    )
    quotes = pd.DataFrame(
        {
            "timestamp": ["2026-05-27 09:29:30", "2026-05-27 09:30:30"],
            "bid": [100.0, 101.0],
        }
    )

    result = align_temporal_asof(
        trades,
        quotes,
        tolerance="45s",
        direction="backward",
        name="trade_quote_alignment",
    )

    assert result.data_status.is_partial is False
    assert result.frame["bid"].tolist() == [100.0, 101.0]
    assert result.frame[DELTA_SECONDS_COLUMN].tolist() == [30.0, 30.0]


def test_temporal_alignment_matches_forward():
    left = pd.DataFrame({"timestamp": ["2026-05-27 09:30:00"], "event": ["news"]})
    right = pd.DataFrame({"timestamp": ["2026-05-27 09:31:00"], "close": [500.0]})

    result = align_temporal_asof(
        left,
        right,
        tolerance="2min",
        direction="forward",
    )

    assert result.frame.loc[0, "close"] == 500.0
    assert bool(result.frame.loc[0, MATCHED_COLUMN]) is True


def test_temporal_alignment_matches_nearest():
    left = pd.DataFrame({"timestamp": ["2026-05-27 09:30:40"], "event": ["filing"]})
    right = pd.DataFrame(
        {
            "timestamp": ["2026-05-27 09:30:00", "2026-05-27 09:31:00"],
            "price": [99.0, 101.0],
        }
    )

    result = align_temporal_asof(
        left,
        right,
        tolerance="1min",
        direction="nearest",
    )

    assert result.frame.loc[0, "price"] == 101.0
    assert result.frame.loc[0, DELTA_SECONDS_COLUMN] == 20.0


def test_temporal_alignment_reports_unmatched_rows_outside_tolerance():
    left = pd.DataFrame({"timestamp": ["2026-05-27 09:30:00"], "event": ["trade"]})
    right = pd.DataFrame({"timestamp": ["2026-05-27 09:25:00"], "price": [99.0]})

    result = align_temporal_asof(
        left,
        right,
        tolerance="1min",
        direction="backward",
    )

    assert result.data_status.is_partial is True
    assert "1/1 rows unmatched" in result.data_status.error
    assert result.quality_warnings


def test_temporal_alignment_groups_by_provider_or_symbol():
    left = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "timestamp": ["2026-05-27 10:00:00", "2026-05-27 10:00:00"],
            "trade": [10, 20],
        }
    )
    right = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "timestamp": ["2026-05-27 09:59:30", "2026-05-27 09:59:30"],
            "quote": [11, 21],
        }
    )

    result = align_temporal_asof(
        left,
        right,
        by="symbol",
        tolerance="1min",
        direction="backward",
    )

    quotes_by_symbol = dict(
        zip(result.frame["symbol"], result.frame["quote"], strict=True)
    )
    assert quotes_by_symbol == {"AAA": 11, "BBB": 21}
    assert result.data_status.cache_status == "computed"
