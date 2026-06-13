from src.display_labels import (
    ACTION_LABELS,
    SECTOR_RATING_LABELS,
    TECHNICAL_LABELS,
    TREND_RATING_LABELS,
)


def test_primary_evaluation_labels_cover_positive_negative_and_neutral_states():
    assert TECHNICAL_LABELS == {
        "Strong Buy": "強い買い優勢",
        "Buy": "買い優勢",
        "Hold": "中立・様子見",
        "Sell": "売り優勢",
        "Strong Sell": "強い売り優勢",
    }
    assert TREND_RATING_LABELS["Robust"] == "堅牢"
    assert TREND_RATING_LABELS["Fragile"] == "脆弱"
    assert TREND_RATING_LABELS["Watch"] == "監視"
    assert ACTION_LABELS["Add small"] == "小さく追加を検討"
    assert ACTION_LABELS["Avoid"] == "見送り"
    assert SECTOR_RATING_LABELS["high"] == "高評価"
    assert SECTOR_RATING_LABELS["weak"] == "弱い"
