from src.themes_config import PERIODS


def test_theme_ranking_periods_do_not_include_removed_short_windows():
    assert "5日" not in PERIODS
    assert "2週間" not in PERIODS
    assert "1週間" in PERIODS
