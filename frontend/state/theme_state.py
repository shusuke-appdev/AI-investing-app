import reflex as rx
import asyncio
from typing import List
from pydantic import BaseModel
from src.themes_config import PERIODS


class ThemeStock(BaseModel):
    """テーマ内の個別銘柄"""
    ticker: str = ""
    display_name: str = ""
    performance: float = 0.0


class ThemeItem(BaseModel):
    """テーマランキングの1行"""
    theme: str = ""
    performance: float = 0.0
    stocks: List[ThemeStock] = []


class ThemeState(rx.State):
    """テーマ（Theme）ページ用の状態管理クラス"""

    selected_period: str = "1w"
    is_fetching: bool = False
    error_msg: str = ""

    # テーマランキングデータ（型付き）
    ranked_themes: List[ThemeItem] = []

    def set_period(self, period: str | List[str]):
        """期間を変更し、データを再取得する"""
        if isinstance(period, list):
            period = period[0] if period else "1w"

        if period in PERIODS:
            self.selected_period = period
            return ThemeState.fetch_themes

    @rx.var
    def periods(self) -> List[str]:
        """選択可能な期間のリスト"""
        return list(PERIODS.keys())

    @rx.var
    def top_10_themes(self) -> List[ThemeItem]:
        """トップ10テーマ（パフォーマンス降順）"""
        if not self.ranked_themes:
            return []
        return self.ranked_themes[:10]

    @rx.var
    def bottom_10_themes(self) -> List[ThemeItem]:
        """ワースト10テーマ（パフォーマンス昇順）"""
        if not self.ranked_themes:
            return []
        bottom_10 = self.ranked_themes[-10:]
        return sorted(bottom_10, key=lambda x: x.performance)

    async def fetch_themes(self):
        """テーマデータを取得する"""
        self.is_fetching = True
        self.error_msg = ""
        yield

        try:
            from src.theme_analyst import get_ranked_themes
            from src.themes_config import get_ticker_name

            market_type = "US"
            themes_data = await asyncio.to_thread(
                get_ranked_themes, self.selected_period, market_type
            )

            if themes_data:
                items: list[ThemeItem] = []
                for t in themes_data:
                    td = dict(t)
                    stocks_out: list[ThemeStock] = []
                    for s in td.get("stocks", []):
                        sd = dict(s)
                        ticker = sd["ticker"]
                        name = get_ticker_name(ticker, market_type)
                        if market_type == "JP" and name != ticker:
                            disp = f"{name} ({ticker.replace('.T', '')})"
                        else:
                            disp = ticker
                        stocks_out.append(
                            ThemeStock(
                                ticker=ticker,
                                display_name=disp,
                                performance=float(sd.get("performance", 0)),
                            )
                        )
                    items.append(
                        ThemeItem(
                            theme=td["theme"],
                            performance=float(td["performance"]),
                            stocks=stocks_out,
                        )
                    )
                self.ranked_themes = items
            else:
                self.ranked_themes = []
                self.error_msg = "テーマデータを取得できませんでした。"

        except Exception as e:
            self.error_msg = f"データの取得に失敗しました: {str(e)}"
            self.ranked_themes = []
        finally:
            self.is_fetching = False
            yield
