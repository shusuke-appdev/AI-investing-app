import pandas as pd

from src import theme_analyst
from src.themes_config import PERIODS


def test_theme_ranking_periods_do_not_include_removed_short_windows():
    assert "5日" not in PERIODS
    assert "2週間" not in PERIODS
    assert "1週間" in PERIODS


def test_theme_performance_skips_ticker_without_full_requested_window(monkeypatch):
    monkeypatch.setattr(theme_analyst, "get_themes", lambda market: {"AI": ["NEW"]})
    monkeypatch.setattr(
        theme_analyst.yf,
        "download",
        lambda *args, **kwargs: pd.DataFrame(
            {"Close": [100.0, 110.0]},
            index=pd.to_datetime(["2026-06-10", "2026-06-13"]),
        ),
    )

    result = theme_analyst.fetch_and_calculate_all_performances(30, "US")

    assert result == {}


def test_theme_ranking_requires_component_count_and_coverage(monkeypatch):
    monkeypatch.setattr(
        theme_analyst,
        "get_themes",
        lambda market: {
            "Covered": ["A", "B", "C", "D"],
            "Too Sparse": ["A", "B", "C", "D", "E", "F"],
            "Too Small": ["A"],
        },
    )
    monkeypatch.setattr(
        theme_analyst,
        "_fetch_performance_observations",
        lambda days, market: {
            "A": {"performance": 10.0, "requested_days": days, "actual_days": days},
            "B": {"performance": 0.0, "requested_days": days, "actual_days": days},
        },
    )

    result = theme_analyst.get_ranked_themes.__wrapped__("1ヶ月", "US")

    assert [item["theme"] for item in result] == ["Covered"]
    assert result[0]["component_count"] == 2
    assert result[0]["total_components"] == 4
    assert result[0]["coverage"] == 0.5
