import asyncio

import reflex as rx
from pydantic import BaseModel

from frontend.state.error_handling import log_state_exception
from frontend.state.request_tracking import is_current_request
from src.log_config import get_logger
from src.themes_config import PERIODS

logger = get_logger(__name__)
THEME_ROUTES = {"/theme"}


class ThemeStock(BaseModel):
    """テーマ内の個別銘柄"""

    ticker: str = ""
    display_name: str = ""
    performance: float = 0.0


class ThemeItem(BaseModel):
    """テーマランキングの1行"""

    theme: str = ""
    performance: float = 0.0
    stocks: list[ThemeStock] = []
    requested_days: int = 0
    component_count: int = 0
    total_components: int = 0
    coverage: float = 0.0
    leader_ticker: str = ""
    leader_display_name: str = ""
    leader_performance: float = 0.0


class ThemeState(rx.State):
    """テーマ（Theme）ページ用の状態管理クラス"""

    selected_period: str = "1週間"
    requested_market_type: str = "US"
    loaded_market_type: str = ""
    loaded_period: str = ""
    loaded_at: str = ""
    is_fetching: bool = False
    error_msg: str = ""
    warning_msg: str = ""
    error_code: str = ""
    theme_request_id: int = 0
    direction_filter: str = "all"
    sort_mode: str = "performance"

    # テーマランキングデータ（型付き）
    ranked_themes: list[ThemeItem] = []

    def set_period(self, period: str | list[str]):
        """期間を変更し、データを再取得する"""
        if isinstance(period, list):
            period = period[0] if period else "1週間"

        if period in PERIODS:
            if period != self.selected_period:
                self.theme_request_id += 1
                self.is_fetching = False
                self.ranked_themes = []
                self.loaded_period = ""
                self.loaded_at = ""
                self.error_msg = ""
                self.warning_msg = ""
                self.error_code = ""
            self.selected_period = period
            return ThemeState.fetch_themes

    def set_market_type(self, market_type: str):
        """Invalidate rankings and refresh only on routes that display themes."""

        if market_type not in {"US", "JP"}:
            return None
        if market_type != self.requested_market_type:
            self.theme_request_id += 1
            self.is_fetching = False
            self.requested_market_type = market_type
            self.loaded_market_type = ""
            self.loaded_period = ""
            self.loaded_at = ""
            self.ranked_themes = []
            self.error_msg = ""
            self.warning_msg = ""
            self.error_code = ""
        if self.router.url.path in THEME_ROUTES:
            return ThemeState.fetch_themes
        return None

    def set_direction_filter(self, value: str | list[str]):
        """上昇・下落の表示対象を切り替える。"""

        if isinstance(value, list):
            value = value[0] if value else "all"
        if value in {"all", "up", "down"}:
            self.direction_filter = value

    def set_sort_mode(self, value: str | list[str]):
        """テーマの並び順をパフォーマンスまたは取得率に切り替える。"""

        if isinstance(value, list):
            value = value[0] if value else "performance"
        if value in {"performance", "coverage"}:
            self.sort_mode = value

    @rx.var
    def periods(self) -> list[str]:
        """選択可能な期間のリスト"""
        return list(PERIODS.keys())

    @rx.var
    def top_10_themes(self) -> list[ThemeItem]:
        """上昇テーマを選択中の基準で並べる。"""

        upward = [item for item in self.ranked_themes if item.performance >= 0]
        key = (
            (lambda item: item.coverage)
            if self.sort_mode == "coverage"
            else (lambda item: item.performance)
        )
        return sorted(upward, key=key, reverse=True)[:10]

    @rx.var
    def bottom_10_themes(self) -> list[ThemeItem]:
        """下落テーマを選択中の基準で並べる。"""

        downward = [item for item in self.ranked_themes if item.performance < 0]
        if self.sort_mode == "coverage":
            return sorted(downward, key=lambda item: item.coverage, reverse=True)[:10]
        return sorted(downward, key=lambda item: item.performance)[:10]

    @rx.var
    def show_upward_column(self) -> bool:
        return self.direction_filter in {"all", "up"}

    @rx.var
    def show_downward_column(self) -> bool:
        return self.direction_filter in {"all", "down"}

    @rx.var
    def requested_market_label(self) -> str:
        return "日本 JP" if self.requested_market_type == "JP" else "米国 US"

    async def fetch_themes(self):
        """テーマデータを取得する"""
        from frontend.state.market_state import MarketState
        from src.theme_analyst import get_ranked_themes_result
        from src.themes_config import get_ticker_name

        market_state = await self.get_state(MarketState)
        market_type = market_state.market_type
        period = self.selected_period
        self.requested_market_type = market_type
        self.theme_request_id += 1
        request_id = self.theme_request_id
        self.is_fetching = True
        self.error_msg = ""
        self.warning_msg = ""
        self.error_code = ""
        yield

        try:
            result = await asyncio.to_thread(
                get_ranked_themes_result, period, market_type
            )
            if not self._is_current_theme_request(
                request_id, market_type, period, market_state.market_type
            ):
                return
            themes_data = result.data

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
                                performance=round(float(sd.get("performance", 0)), 1),
                            )
                        )
                    leader = max(
                        stocks_out,
                        key=lambda stock: stock.performance,
                        default=ThemeStock(),
                    )
                    items.append(
                        ThemeItem(
                            theme=td["theme"],
                            performance=round(float(td["performance"]), 1),
                            stocks=stocks_out,
                            requested_days=int(td.get("requested_days", 0)),
                            component_count=int(td.get("component_count", 0)),
                            total_components=int(td.get("total_components", 0)),
                            coverage=round(float(td.get("coverage", 0.0)) * 100, 1),
                            leader_ticker=leader.ticker,
                            leader_display_name=leader.display_name,
                            leader_performance=leader.performance,
                        )
                    )
                self.ranked_themes = items
                self.loaded_market_type = market_type
                self.loaded_period = period
                self.loaded_at = result.fetched_at
                self.warning_msg = " ".join(result.warnings)
            else:
                self.ranked_themes = []
                self.loaded_market_type = ""
                self.loaded_period = ""
                self.loaded_at = result.fetched_at
                self.error_code = result.error_code or "unavailable"
                if self.error_code == "insufficient_coverage":
                    self.error_msg = (
                        "対象期間に必要な銘柄数または取得率を満たすテーマがありません。"
                    )
                else:
                    self.error_msg = "テーマデータを取得できませんでした。時間をおいて再試行してください。"
                if result.error:
                    logger.warning(
                        "Theme ranking unavailable [error_code=%s]",
                        self.error_code,
                    )

        except Exception as exc:
            if not self._is_current_theme_request(
                request_id, market_type, period, market_state.market_type
            ):
                return
            error = log_state_exception(logger, "テーマデータの取得", exc)
            self.error_code = error.code
            self.error_msg = error.message
            self.ranked_themes = []
            self.loaded_market_type = ""
            self.loaded_period = ""
        finally:
            if self._is_current_theme_request(
                request_id, market_type, period, market_state.market_type
            ):
                self.is_fetching = False
                yield

    def _is_current_theme_request(
        self,
        request_id: int,
        market_type: str,
        period: str,
        current_market_type: str,
    ) -> bool:
        return (
            is_current_request(
                current_id=self.theme_request_id,
                current_key=f"{self.requested_market_type}:{self.selected_period}",
                request_id=request_id,
                request_key=f"{market_type}:{period}",
            )
            and current_market_type == market_type
        )
