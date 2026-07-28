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


def test_theme_ranking_result_preserves_provider_failure(monkeypatch):
    monkeypatch.setattr(
        theme_analyst,
        "get_themes",
        lambda market: {"Covered": ["A", "B"]},
    )

    def fail_download(*args, **kwargs):
        raise ConnectionError("https://provider.invalid/?token=secret")

    monkeypatch.setattr(theme_analyst.yf, "download", fail_download)

    result = theme_analyst.get_ranked_themes_result.__wrapped__("1ヶ月", "US")

    assert result.data == []
    assert result.status == "unavailable"
    assert result.error_code == "provider_error"
    assert "token=secret" in result.error


def test_ranked_theme_periods_reuses_one_download_for_all_periods(monkeypatch):
    calls = []
    dates = pd.date_range("2024-01-01", periods=820, freq="D")
    frame = pd.DataFrame(
        {
            ("A", "Close"): [100.0 + index * 0.1 for index in range(len(dates))],
            ("B", "Close"): [90.0 + index * 0.08 for index in range(len(dates))],
        },
        index=dates,
    )
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    monkeypatch.setattr(theme_analyst, "get_themes", lambda market: {"AI": ["A", "B"]})

    def fake_download(*args, **kwargs):
        calls.append(kwargs.get("period"))
        return frame

    monkeypatch.setattr(theme_analyst.yf, "download", fake_download)

    result = theme_analyst.get_ranked_theme_periods.__wrapped__(
        ("1週間", "1ヶ月", "6ヶ月", "24ヶ月"), "US"
    )

    assert calls == ["2y"]
    assert set(result) == {"1週間", "1ヶ月", "6ヶ月", "24ヶ月"}
    assert all(rows[0]["theme"] == "AI" for rows in result.values())
