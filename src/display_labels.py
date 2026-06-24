"""Central Japanese display labels for analysis outputs."""

TECHNICAL_LABELS = {
    "Strong Buy": "強い強気",
    "Buy": "強気",
    "Hold": "中立",
    "Sell": "弱気",
    "Strong Sell": "強い弱気",
}

ACTION_LABELS = {
    "Add small": "強気根拠あり",
    "Hold": "中立継続",
    "Watch": "確認継続",
    "Avoid": "リスク警戒",
}

SIGNAL_LABELS = {
    "Neutral": "中立",
    "Insufficient data": "データ不足",
    "Strong Oversold Rebound Candidate": "強い売られすぎ反発候補",
    "Oversold Rebound Candidate": "売られすぎ反発候補",
    "Strong Overbought Mean-Reversion Candidate": "強い買われすぎ反落候補",
    "Overbought Mean-Reversion Candidate": "買われすぎ反落候補",
}

CONFIDENCE_LABELS = {"High": "高", "Medium": "中", "Low": "低"}

TREND_RATING_LABELS = {
    "Fragile": "脆弱",
    "Robust": "堅牢",
    "Watch": "監視",
    "Unavailable": "算出不可",
    "Unproven": "未検証",
}

SECTOR_RATING_LABELS = {
    "high": "高評価",
    "conditional": "条件付き",
    "weak": "弱い",
    "unavailable": "算出不可",
}


def display_label(value: str, mapping: dict[str, str]) -> str:
    return mapping.get(value, value)
