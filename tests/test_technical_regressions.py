import pandas as pd

from src.advisor.technical import calculate_long_term_ma


def test_missing_500_and_750_day_ma_do_not_create_false_support_signal():
    close = pd.Series(range(1, 301), dtype=float)

    result = calculate_long_term_ma(close)

    assert result["ma_250"] is not None
    assert result["ma_500"] is None
    assert result["ma_750"] is None
    assert result["signal"] == "neutral"
