import pandas as pd

from src.advisor.minervini_analyzer import analyze_stage


def _frame(closes: list[float]) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=len(closes), freq="D")
    close = pd.Series(closes, index=index)
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": [1_000_000] * len(closes),
        },
        index=index,
    )


def test_minervini_stage2_exposes_template_conditions():
    result = analyze_stage(_frame([50 + index * 0.5 for index in range(260)]))

    assert result["stage"] == 2
    assert result["label"] == "ステージ2"
    assert result["stage2_pass_count"] == result["stage2_total_count"]
    assert result["ma50"] is not None
    assert result["ma150"] is not None
    assert result["ma200"] is not None
    assert result["ma200_rising"] is True
    assert result["pct_above_low_52w"] is not None
    assert result["pct_below_high_52w"] is not None
    assert all(item["status"] == "pass" for item in result["conditions"])


def test_minervini_stage4_is_explicitly_labeled():
    result = analyze_stage(_frame([180 - index * 0.5 for index in range(260)]))

    assert result["stage"] == 4
    assert result["label"] == "ステージ4"
    assert result["warnings"]


def test_minervini_stage1_base_building_is_explicitly_labeled():
    result = analyze_stage(_frame([100.0] * 260))

    assert result["stage"] == 1
    assert result["label"] == "ステージ1"
    assert result["ma200_rising"] is False


def test_minervini_stage3_distribution_is_explicitly_labeled():
    closes = [60 + index * 0.45 for index in range(220)]
    closes += [159 - index * 1.8 for index in range(40)]

    result = analyze_stage(_frame(closes))

    assert result["stage"] == 3
    assert result["label"] == "ステージ3"
    assert result["stage2_pass_count"] < result["stage2_total_count"]


def test_minervini_stage_unavailable_preserves_display_shape():
    result = analyze_stage(_frame([100.0] * 80))

    assert result["stage"] == 0
    assert result["label"] == "判定不能"
    assert result["conditions"] == []
    assert result["warnings"]
