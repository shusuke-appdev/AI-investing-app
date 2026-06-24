from src.display_labels import (
    ACTION_LABELS,
    SECTOR_RATING_LABELS,
    TECHNICAL_LABELS,
    TREND_RATING_LABELS,
)


def test_primary_evaluation_labels_cover_positive_negative_and_neutral_states():
    assert TECHNICAL_LABELS == {
        "Strong Buy": "強い強気",
        "Buy": "強気",
        "Hold": "中立",
        "Sell": "弱気",
        "Strong Sell": "強い弱気",
    }
    assert TREND_RATING_LABELS["Robust"] == "堅牢"
    assert TREND_RATING_LABELS["Fragile"] == "脆弱"
    assert TREND_RATING_LABELS["Watch"] == "監視"
    assert ACTION_LABELS["Add small"] == "強気根拠あり"
    assert ACTION_LABELS["Avoid"] == "リスク警戒"
    assert SECTOR_RATING_LABELS["high"] == "高評価"
    assert SECTOR_RATING_LABELS["weak"] == "弱い"
