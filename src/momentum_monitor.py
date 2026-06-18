"""
テーマモメンタム監視モジュール
4カテゴリ（超短期/短期/中期/長期）のテーマモメンタムランキングを提供。
"""

from src.cache import ttl_cache
from src.log_config import get_logger
from src.theme_analyst import get_ranked_theme_periods

logger = get_logger(__name__)

# 4カテゴリ定義: カテゴリ名 → テーマ期間名
MOMENTUM_CATEGORIES: dict[str, str] = {
    "超短期 (1W)": "1週間",
    "短期 (1M)": "1ヶ月",
    "中期 (6M)": "6ヶ月",
    "長期 (24M)": "24ヶ月",
}


@ttl_cache(ttl=43200)  # 12時間キャッシュ
def get_momentum_themes(
    market_type: str = "US", top_n: int = 5
) -> dict[str, list[dict]]:
    """
    4カテゴリ×上位N・下位Nテーマのモメンタムランキングを取得する。

    リスト先頭は上位、末尾は下位になる。表示層は先頭だけを表示し、
    AIレポートは両端を使ってleaders/laggardsを区別する。

    Args:
        market_type: "US" または "JP"
        top_n: 各カテゴリで返すテーマ数

    Returns:
        {カテゴリ名: [{"theme": str, "performance": float, "period": str}, ...]}
    """
    result: dict[str, list[dict]] = {}

    try:
        period_rankings = get_ranked_theme_periods(
            tuple(MOMENTUM_CATEGORIES.values()), market_type
        )
    except Exception as e:
        logger.warning("[MomentumMonitor] Failed to get batched rankings: %s", e)
        period_rankings = {}
    for cat_name, period_name in MOMENTUM_CATEGORIES.items():
        try:
            ranked = period_rankings.get(period_name, [])
            selected = ranked[:top_n]
            if len(ranked) > top_n:
                selected += ranked[-top_n:]
            themes = []
            seen: set[str] = set()
            for t in selected:
                theme_name = str(t["theme"])
                if theme_name in seen:
                    continue
                seen.add(theme_name)
                themes.append(
                    {
                        "theme": theme_name,
                        "performance": round(t["performance"], 1),
                        "period": period_name,
                    }
                )
            result[cat_name] = themes
        except Exception as e:
            logger.warning(
                f"[MomentumMonitor] Failed to get themes for {cat_name}: {e}"
            )
            result[cat_name] = []

    return result
