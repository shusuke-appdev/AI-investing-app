import asyncio

import reflex as rx
from pydantic import BaseModel

from frontend.state.error_handling import log_state_exception
from frontend.state.request_tracking import is_current_request
from src.log_config import get_logger
from src.themes_config import PERIODS

logger = get_logger(__name__)
THEME_ROUTES = {"/theme", "/theme-leaders"}


class ThemeStock(BaseModel):
    """テーマ内の個別銘柄"""

    ticker: str = ""
    display_name: str = ""
    performance: float = 0.0


class ThemeItem(BaseModel):
    """テーマランキングの1行"""

    theme: str = ""
    performance: float = 0.0
    total_score: float = 0.0
    momentum_score: float = 0.0
    relative_strength_score: float = 0.0
    attention_score: float = 0.0
    breadth_score: float = 0.0
    performance_1w: float = 0.0
    performance_1m: float = 0.0
    performance_6m: float = 0.0
    rank: int = 0
    rank_1w: int = 0
    rank_1m: int = 0
    rank_6m: int = 0
    rank_acceleration: int = 0
    coverage_1w: float = 0.0
    coverage_1m: float = 0.0
    coverage_6m: float = 0.0
    proxy_ticker: str = ""
    proxy_confirmation: str = ""
    data_quality: str = ""
    stocks: list[ThemeStock] = []
    requested_days: int = 0
    component_count: int = 0
    total_components: int = 0
    coverage: float = 0.0
    leader_ticker: str = ""
    leader_display_name: str = ""
    leader_performance: float = 0.0


class ThemeLeaderCondition(BaseModel):
    """ステージ2の1条件。"""

    key: str = ""
    label: str = ""
    status: str = ""
    value: str = ""
    rationale: str = ""


class ThemeLeaderCandidate(BaseModel):
    """テーマ主導で抽出した追加調査候補。"""

    ticker: str = ""
    primary_theme: str = ""
    themes_display: str = ""
    status: str = ""
    score: float = 0.0
    research_priority_score: float = 0.0
    candidate_source: str = ""
    source_urls: list[str] = []
    company_name: str = ""
    fundamental_status: str = ""
    fundamental_category: str = ""
    fundamental_score: float = 0.0
    fundamental_coverage: float = 0.0
    fundamental_summary: str = ""
    median_dollar_volume_20d: float = 0.0
    stage_pass_count: int = 0
    stage_conditions: list[ThemeLeaderCondition] = []
    market_relative_20d: float = 0.0
    market_relative_63d: float = 0.0
    theme_relative_20d: float = 0.0
    theme_relative_63d: float = 0.0
    rs_line_near_high: bool = False
    vcp: bool = False
    atr_contraction: bool = False
    pivot_price: float = 0.0
    pivot_distance_pct: float = 0.0
    rvol: float = 0.0
    volume_contraction: bool = False
    ma50_extension_atr: float = 0.0
    rank: int = 0
    rank_1w: int = 0
    rank_1m: int = 0
    rank_6m: int = 0
    rank_acceleration: int = 0
    coverage_1w: float = 0.0
    coverage_1m: float = 0.0
    coverage_6m: float = 0.0
    performance_1w: float = 0.0
    performance_1m: float = 0.0
    performance_6m: float = 0.0
    theme_score: float = 0.0
    stage_score: float = 0.0
    relative_score: float = 0.0
    setup_score: float = 0.0
    candidate_reason: str = ""
    next_condition: str = ""
    invalidation_condition: str = ""
    data_quality: str = ""
    fetched_at: str = ""


class ThemeLeaderExclusion(BaseModel):
    """候補から外した理由と件数。"""

    reason: str = ""
    count: int = 0


class GeminiUnverifiedTicker(BaseModel):
    ticker: str = ""
    theme: str = ""
    company_name: str = ""
    reason: str = ""
    source_urls: list[str] = []


class ThemeDeepDiveItem(BaseModel):
    ticker: str = ""
    business_relationship: str = ""
    earnings_acceleration: str = ""
    latest_catalyst: str = ""
    counter_evidence: str = ""
    next_check: str = ""
    source_urls: list[str] = []


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
    leader_request_id: int = 0
    direction_filter: str = "all"
    sort_mode: str = "performance"

    # テーマランキングデータ（型付き）
    ranked_themes: list[ThemeItem] = []
    leader_candidates: list[ThemeLeaderCandidate] = []
    leader_fundamental_pending: list[ThemeLeaderCandidate] = []
    leader_gemini_unverified: list[GeminiUnverifiedTicker] = []
    leader_exclusions: list[ThemeLeaderExclusion] = []
    leader_selected_themes: list[str] = []
    leader_status: str = "idle"
    leader_loaded_at: str = ""
    leader_warning_msg: str = ""
    leader_error_msg: str = ""
    is_discovering_leaders: bool = False
    gemini_status: str = "idle"
    gemini_model: str = ""
    gemini_total_tokens: int = 0
    gemini_search_query_count: int = 0
    gemini_cache_status: str = ""
    deep_dive_items: list[ThemeDeepDiveItem] = []
    deep_dive_status: str = "idle"
    deep_dive_error_msg: str = ""
    is_deep_diving: bool = False

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
            self.leader_request_id += 1
            self.is_fetching = False
            self.requested_market_type = market_type
            self.loaded_market_type = ""
            self.loaded_period = ""
            self.loaded_at = ""
            self.ranked_themes = []
            self.error_msg = ""
            self.warning_msg = ""
            self.error_code = ""
            self._clear_leader_discovery()
        if self.router.url.path == "/theme":
            return ThemeState.fetch_themes
        if self.router.url.path == "/theme-leaders":
            return ThemeState.prepare_theme_leaders
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
        from src.services.comprehensive_theme_ranking_service import (
            get_comprehensive_theme_ranking_result,
        )
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
                get_comprehensive_theme_ranking_result, market_type
            )
            if not self._is_current_theme_request(
                request_id, market_type, period, market_state.market_type
            ):
                return
            context = result.data
            themes_data = list(context.get("items") or [])

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
                            performance=round(float(td.get("performance_1w") or 0), 1),
                            total_score=round(float(td.get("total_score") or 0), 1),
                            momentum_score=round(
                                float(td.get("momentum_score") or 0), 1
                            ),
                            relative_strength_score=round(
                                float(td.get("relative_strength_score") or 0), 1
                            ),
                            attention_score=round(
                                float(td.get("attention_score") or 0), 1
                            ),
                            breadth_score=round(float(td.get("breadth_score") or 0), 1),
                            performance_1w=round(
                                float(td.get("performance_1w") or 0), 1
                            ),
                            performance_1m=round(
                                float(td.get("performance_1m") or 0), 1
                            ),
                            performance_6m=round(
                                float(td.get("performance_6m") or 0), 1
                            ),
                            rank=int(td.get("rank") or 0),
                            rank_1w=int(td.get("rank_1w") or 0),
                            rank_1m=int(td.get("rank_1m") or 0),
                            rank_6m=int(td.get("rank_6m") or 0),
                            rank_acceleration=int(td.get("rank_acceleration") or 0),
                            coverage_1w=round(
                                float(td.get("coverage_1w") or 0) * 100, 1
                            ),
                            coverage_1m=round(
                                float(td.get("coverage_1m") or 0) * 100, 1
                            ),
                            coverage_6m=round(
                                float(td.get("coverage_6m") or 0) * 100, 1
                            ),
                            stocks=stocks_out,
                            component_count=int(td.get("component_count", 0)),
                            total_components=int(td.get("total_components", 0)),
                            coverage=round(float(td.get("coverage_1m") or 0) * 100, 1),
                            proxy_ticker=str(td.get("proxy_ticker") or ""),
                            proxy_confirmation=str(td.get("proxy_confirmation") or ""),
                            data_quality=str(td.get("data_quality") or ""),
                            leader_ticker=leader.ticker,
                            leader_display_name=leader.display_name,
                            leader_performance=leader.performance,
                        )
                    )
                self.ranked_themes = items
                self.loaded_market_type = market_type
                self.loaded_period = period
                self.loaded_at = result.fetched_at
                self.warning_msg = " ".join(
                    [*result.warnings, *context.get("quality_warnings", [])]
                )
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

    async def prepare_theme_leaders(self):
        """Select the requested themes and read cache only; never start analysis."""

        from frontend.state.market_state import MarketState
        from src.services.theme_leader_service import (
            get_cached_theme_leader_discovery_result,
        )

        market_state = await self.get_state(MarketState)
        self.requested_market_type = market_state.market_type
        route_theme = str(self.router.page.params.get("theme", "") or "").strip()
        if route_theme:
            self.leader_selected_themes = [route_theme]
        else:
            top = sorted(self.ranked_themes, key=lambda item: item.rank or 10_000)[:3]
            accelerating = sorted(
                [item for item in self.ranked_themes if item.rank_acceleration >= 5],
                key=lambda item: (-item.rank_acceleration, item.rank_1w, item.theme),
            )[:2]
            self.leader_selected_themes = list(
                dict.fromkeys([item.theme for item in [*top, *accelerating]])
            )[:5]
        self._clear_leader_results(preserve_selection=True)
        result = await asyncio.to_thread(
            get_cached_theme_leader_discovery_result,
            market_state.market_type,
            self.leader_selected_themes or None,
        )
        if result.is_available:
            self._apply_leader_context(result.data, result.fetched_at, result.warnings)

    async def discover_theme_leaders(self, force_refresh: bool = False):
        """明示操作時だけ、テーマ主導の次期リーダー候補を分析する。"""

        from frontend.state.market_state import MarketState
        from src.services.theme_leader_service import (
            get_theme_leader_discovery_result,
        )

        market_state = await self.get_state(MarketState)
        market_type = market_state.market_type
        self.requested_market_type = market_type
        self.leader_request_id += 1
        request_id = self.leader_request_id
        self.is_discovering_leaders = True
        self.leader_error_msg = ""
        self.leader_warning_msg = ""
        self.leader_status = "loading"
        yield

        try:
            result = await asyncio.to_thread(
                get_theme_leader_discovery_result,
                market_type,
                self.leader_selected_themes or None,
                force_refresh=force_refresh,
            )
            if not self._is_current_leader_request(
                request_id, market_type, market_state.market_type
            ):
                return
            context = result.data
            self._apply_leader_context(context, result.fetched_at, result.warnings)
            if not self.leader_candidates and result.error_code not in {
                "",
                "no_eligible_candidates",
            }:
                self.leader_error_msg = "候補分析に必要なデータを取得できませんでした。テーマランキングはそのまま利用できます。"
        except Exception as exc:
            if not self._is_current_leader_request(
                request_id, market_type, market_state.market_type
            ):
                return
            error = log_state_exception(logger, "次期リーダー候補の分析", exc)
            self.leader_status = "error"
            self.leader_error_msg = error.message
            self.leader_candidates = []
        finally:
            if self._is_current_leader_request(
                request_id, market_type, market_state.market_type
            ):
                self.is_discovering_leaders = False
                yield

    async def deep_dive_theme_leaders(self, force_refresh: bool = False):
        """Run a separate grounded review for the current machine-ranked top five."""

        from src.services.theme_grounded_research_service import (
            deep_dive_theme_candidates,
        )

        if not self.leader_candidates:
            return
        self.is_deep_diving = True
        self.deep_dive_status = "loading"
        self.deep_dive_error_msg = ""
        yield
        payload = [item.model_dump() for item in self.leader_candidates[:5]]
        try:
            context = await asyncio.to_thread(
                deep_dive_theme_candidates,
                self.requested_market_type,
                payload,
                force_refresh=force_refresh,
            )
            self.deep_dive_items = [
                ThemeDeepDiveItem(**item) for item in context.get("items", [])
            ]
            self.deep_dive_status = str(context.get("status") or "unavailable")
            self.gemini_total_tokens = int(context.get("total_tokens") or 0)
            self.gemini_search_query_count = int(context.get("search_query_count") or 0)
            if context.get("error"):
                self.deep_dive_error_msg = str(context["error"])
        except Exception as exc:
            error = log_state_exception(logger, "候補のGemini深掘り", exc)
            self.deep_dive_status = "error"
            self.deep_dive_error_msg = error.message
        finally:
            self.is_deep_diving = False
            yield

    def _apply_leader_context(
        self, context: dict, fetched_at: str, warnings: list[str]
    ) -> None:
        self.leader_candidates = [
            self._leader_candidate_from_payload(item)
            for item in context.get("candidates", [])
        ]
        self.leader_fundamental_pending = [
            self._leader_candidate_from_payload(item)
            for item in context.get("fundamental_pending", [])
        ]
        self.leader_gemini_unverified = [
            GeminiUnverifiedTicker(**item)
            for item in context.get("gemini_unverified", [])
        ]
        self.leader_exclusions = [
            ThemeLeaderExclusion(reason=str(reason), count=int(count))
            for reason, count in context.get("excluded_reasons", {}).items()
            if int(count) > 0
        ]
        selected = [
            str(item.get("theme") or "")
            for item in context.get("selected_themes", [])
            if item.get("theme")
        ]
        if selected:
            self.leader_selected_themes = selected
        self.leader_loaded_at = fetched_at or str(context.get("fetched_at") or "")
        self.leader_warning_msg = " ".join([*warnings, *context.get("warnings", [])])
        self.leader_status = str(context.get("status") or "unavailable")
        self.gemini_status = str(context.get("gemini_status") or "unavailable")
        self.gemini_model = str(context.get("gemini_model") or "")
        self.gemini_total_tokens = int(context.get("gemini_total_tokens") or 0)
        self.gemini_search_query_count = int(
            context.get("gemini_search_query_count") or 0
        )
        self.gemini_cache_status = str(context.get("gemini_cache_status") or "")

    @staticmethod
    def _leader_candidate_from_payload(payload: dict) -> ThemeLeaderCandidate:
        score = payload.get("score_breakdown") or {}
        return ThemeLeaderCandidate(
            **{
                key: value
                for key, value in payload.items()
                if key
                not in {
                    "themes",
                    "score_breakdown",
                    "stage_total_count",
                    "market_type",
                }
            },
            themes_display=" / ".join(payload.get("themes") or []),
            theme_score=float(score.get("theme_strength") or 0),
            stage_score=float(score.get("stage2_fit") or 0),
            relative_score=float(score.get("relative_strength") or 0),
            setup_score=float(score.get("setup_readiness") or 0),
        )

    def _clear_leader_discovery(self) -> None:
        self._clear_leader_results(preserve_selection=False)

    def _clear_leader_results(self, *, preserve_selection: bool) -> None:
        self.leader_candidates = []
        self.leader_fundamental_pending = []
        self.leader_gemini_unverified = []
        self.leader_exclusions = []
        if not preserve_selection:
            self.leader_selected_themes = []
        self.leader_status = "idle"
        self.leader_loaded_at = ""
        self.leader_warning_msg = ""
        self.leader_error_msg = ""
        self.is_discovering_leaders = False
        self.gemini_status = "idle"
        self.gemini_model = ""
        self.gemini_total_tokens = 0
        self.gemini_search_query_count = 0
        self.gemini_cache_status = ""
        self.deep_dive_items = []
        self.deep_dive_status = "idle"
        self.deep_dive_error_msg = ""
        self.is_deep_diving = False

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

    def _is_current_leader_request(
        self,
        request_id: int,
        market_type: str,
        current_market_type: str,
    ) -> bool:
        return (
            is_current_request(
                current_id=self.leader_request_id,
                current_key=self.requested_market_type,
                request_id=request_id,
                request_key=market_type,
            )
            and current_market_type == market_type
        )
