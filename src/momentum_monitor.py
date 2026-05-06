"""
テーマモメンタム監視モジュール
4カテゴリ（超短期/短期/中期/長期）のテーマモメンタムランキングを提供。
"""

from src.cache import ttl_cache
from src.log_config import get_logger
from src.theme_analyst import get_ranked_themes

logger = get_logger(__name__)

# 4カテゴリ定義: カテゴリ名 → テーマ期間名
MOMENTUM_CATEGORIES: dict[str, str] = {
    "超短期 (1W)": "1週間",
    "短期 (1M)": "1ヶ月",
    "中期 (6M)": "6ヶ月",
    "長期 (24M)": "24ヶ月",
}


@ttl_cache(ttl=43200)  # 12時間キャッシュ
def get_momentum_themes(market_type: str = "US", top_n: int = 5) -> dict[str, list[dict]]:
    """
    4カテゴリ×上位Nテーマのモメンタムランキングを取得する。

    Args:
        market_type: "US" または "JP"
        top_n: 各カテゴリで返すテーマ数

    Returns:
        {カテゴリ名: [{"theme": str, "performance": float, "period": str}, ...]}
    """
    result: dict[str, list[dict]] = {}

    for cat_name, period_name in MOMENTUM_CATEGORIES.items():
        try:
            ranked = get_ranked_themes(period_name, market_type)
            top_themes = []
            for t in ranked[:top_n]:
                top_themes.append({
                    "theme": t["theme"],
                    "performance": round(t["performance"], 1),
                    "period": period_name,
                })
            result[cat_name] = top_themes
        except Exception as e:
            logger.warning(f"[MomentumMonitor] Failed to get themes for {cat_name}: {e}")
            result[cat_name] = []

    return result
