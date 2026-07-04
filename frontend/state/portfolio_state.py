import asyncio
from typing import Any

import reflex as rx
from pydantic import BaseModel

from frontend.components.data_provenance import (
    ProvenanceDisplay,
    provenance_display_items,
)
from src.services.portfolio_dashboard_service import (
    holdings_to_payload,
    run_portfolio_analysis,
    validate_holding_input,
)


class HoldingItem(BaseModel):
    """ポートフォリオ内の個別銘柄"""

    ticker: str = ""
    shares: float = 0.0
    avg_cost: float | None = None


class PortfolioState(rx.State):
    """ポートフォリオ管理ページ用の状態管理クラス"""

    # ポートフォリオ一覧
    portfolio_names: list[str] = []
    current_portfolio_name: str = "新規ポートフォリオ"

    # 保有銘柄一覧
    holdings: list[HoldingItem] = []

    # 入力用
    new_ticker: str = ""
    new_shares: str = ""
    new_cost: str = ""
    save_name: str = ""

    # 分析結果
    analysis_result: dict[str, Any] = {}
    provenance: list[ProvenanceDisplay] = []
    analysis_warnings: list[str] = []
    ai_advice: str = ""

    # UI状態
    is_loading: bool = False
    is_analyzing: bool = False
    is_generating_advice: bool = False
    error_msg: str = ""
    success_msg: str = ""
    submode: str = "input"  # "input" or "analysis"

    # 現在の共通ストレージ設定をUIに表示するためのミラー
    storage_type: str = "local"
    storage_options: list[str] = ["local", "supabase"]

    def set_submode(self, mode: str):
        self.submode = mode

    def set_new_ticker(self, value: str):
        self.new_ticker = value.upper()

    def set_new_shares(self, value: str):
        self.new_shares = value

    def set_new_cost(self, value: str):
        self.new_cost = value

    def set_save_name(self, value: str):
        self.save_name = value

    @rx.var
    def storage_type_label(self) -> str:
        return storage_type_label(self.storage_type)

    def _sync_storage_type(self) -> None:
        self.storage_type = get_active_storage_type()

    async def load_portfolio_list(self):
        """保存済みポートフォリオ一覧を取得"""
        try:
            self._sync_storage_type()
            from src.portfolio_storage import list_portfolios

            names = await asyncio.to_thread(list_portfolios)
            self.portfolio_names = names
        except Exception as e:
            self.error_msg = f"ポートフォリオ一覧の取得に失敗: {e}"

    async def load_portfolio_list_for_route(self):
        """Load route data only when personal-data pages are enabled."""

        if not _personal_data_route_enabled():
            self._sync_storage_type()
            self.portfolio_names = []
            self.error_msg = ""
            return
        await self.load_portfolio_list()

    async def change_storage_type(self, value: str | list[str]):
        """共通ストレージ設定を変更し、選択先のポートフォリオ一覧を読み直す"""

        if isinstance(value, list):
            value = value[0] if value else ""
        if value not in {"local", "supabase"}:
            self.error_msg = "保存先は local または supabase を選択してください"
            return

        self.is_loading = True
        self.error_msg = ""
        yield

        try:
            from src.settings_storage import set_storage_type_setting

            success = await asyncio.to_thread(set_storage_type_setting, value)
            if not success:
                self.error_msg = "保存先設定の更新に失敗しました"
                return
            self.storage_type = value
            self.current_portfolio_name = "新規ポートフォリオ"
            self.holdings = []
            self.analysis_result = {}
            self.provenance = []
            self.analysis_warnings = []
            self.ai_advice = ""
            from src.portfolio_storage import list_portfolios

            self.portfolio_names = await asyncio.to_thread(list_portfolios)
            self.success_msg = f"保存先を「{storage_type_label(value)}」に変更しました"
        except Exception as e:
            self.error_msg = f"保存先設定エラー: {e}"
        finally:
            self.is_loading = False
            yield

    async def select_portfolio(self, name: str):
        """既存ポートフォリオを選択して読み込む"""
        self.is_loading = True
        self.error_msg = ""
        yield

        try:
            self._sync_storage_type()
            from src.portfolio_storage import load_portfolio

            data = await asyncio.to_thread(load_portfolio, name)
            if data:
                raw_holdings = data.get("holdings", [])
                self.holdings = [
                    HoldingItem(
                        ticker=h.get("ticker", ""),
                        shares=float(h.get("shares", 0)),
                        avg_cost=float(h["avg_cost"])
                        if h.get("avg_cost") is not None
                        else None,
                    )
                    for h in raw_holdings
                ]
                self.current_portfolio_name = name
                self.success_msg = f"「{name}」を読み込みました"
            else:
                self.error_msg = f"「{name}」の読み込みに失敗しました"
        except Exception as e:
            self.error_msg = f"読み込みエラー: {e}"
        finally:
            self.is_loading = False
            yield

    def add_holding(self):
        """銘柄を追加する"""
        validated = validate_holding_input(
            self.new_ticker, self.new_shares, self.new_cost
        )
        if not validated.is_valid:
            self.error_msg = validated.error
            self.success_msg = ""
            return

        # 既存の同一ティッカーがあれば更新
        for i, h in enumerate(self.holdings):
            if h.ticker == validated.ticker:
                self.holdings[i] = HoldingItem(
                    ticker=validated.ticker,
                    shares=validated.shares,
                    avg_cost=validated.avg_cost,
                )
                self.new_ticker = ""
                self.new_shares = ""
                self.new_cost = ""
                self.error_msg = ""
                self.success_msg = f"{validated.ticker} を更新しました"
                return

        self.holdings.append(
            HoldingItem(
                ticker=validated.ticker,
                shares=validated.shares,
                avg_cost=validated.avg_cost,
            )
        )
        self.error_msg = ""
        self.success_msg = f"{validated.ticker} を追加しました"
        self.new_ticker = ""
        self.new_shares = ""
        self.new_cost = ""

    def remove_holding(self, ticker: str):
        """銘柄を削除する"""
        self.holdings = [h for h in self.holdings if h.ticker != ticker]

    async def save_portfolio(self):
        """現在の保有情報をポートフォリオとして保存"""
        name = self.save_name or self.current_portfolio_name
        if name == "新規ポートフォリオ" and not self.save_name:
            self.error_msg = "ポートフォリオ名を入力してください"
            return

        self.is_loading = True
        self.error_msg = ""
        yield

        try:
            self._sync_storage_type()
            from src.portfolio_storage import save_portfolio

            holdings_data = holdings_to_payload(self.holdings)
            if not holdings_data:
                self.error_msg = "保存できる保有銘柄がありません"
                return
            success = await asyncio.to_thread(save_portfolio, name, holdings_data)
            if success:
                self.current_portfolio_name = name
                self.success_msg = (
                    f"「{name}」を{storage_type_label(self.storage_type)}へ保存しました"
                )
                # リストを更新
                from src.portfolio_storage import list_portfolios

                self.portfolio_names = await asyncio.to_thread(list_portfolios)
            else:
                self.error_msg = "保存に失敗しました"
        except Exception as e:
            self.error_msg = f"保存エラー: {e}"
        finally:
            self.is_loading = False
            yield

    async def delete_current_portfolio(self):
        """現在選択中のポートフォリオを削除"""
        if self.current_portfolio_name == "新規ポートフォリオ":
            return

        self.is_loading = True
        yield

        try:
            self._sync_storage_type()
            from src.portfolio_storage import delete_portfolio

            deleted = await asyncio.to_thread(
                delete_portfolio, self.current_portfolio_name
            )
            if not deleted:
                raise ValueError("削除対象が存在しないか、削除に失敗しました")
            self.holdings = []
            self.current_portfolio_name = "新規ポートフォリオ"
            self.success_msg = "ポートフォリオを削除しました"
            from src.portfolio_storage import list_portfolios

            self.portfolio_names = await asyncio.to_thread(list_portfolios)
        except Exception as e:
            self.error_msg = f"削除エラー: {e}"
        finally:
            self.is_loading = False
            yield

    async def run_analysis(self):
        """ポートフォリオ分析を実行"""
        if not self.holdings:
            self.error_msg = "銘柄を追加してから分析してください"
            return

        self.is_analyzing = True
        self.error_msg = ""
        yield

        try:
            holdings_data = holdings_to_payload(self.holdings)
            result = await asyncio.to_thread(run_portfolio_analysis, holdings_data)
            if result:
                self.analysis_result = result
                self.provenance = provenance_display_items(result.get("provenance", []))
                self.analysis_warnings = list(result.get("quality_warnings", []))
                from src.services.analysis_context import DataResult
                from src.services.provider_health import record_data_results

                record_data_results(
                    [
                        DataResult(
                            name="portfolio_analysis",
                            source="market_data providers",
                            is_partial=bool(self.analysis_warnings),
                            error="; ".join(self.analysis_warnings[:3]),
                            cache_status="computed",
                        )
                    ],
                    scope="portfolio",
                )
                self.submode = "analysis"
            else:
                self.error_msg = "分析結果を取得できませんでした"
        except Exception as e:
            self.error_msg = f"分析エラー: {e}"
        finally:
            self.is_analyzing = False
            yield

    async def generate_advice(self):
        """AIアドバイスを生成"""
        if not self.analysis_result:
            self.error_msg = "先に分析を実行してください"
            return

        self.is_generating_advice = True
        self.error_msg = ""
        yield

        try:
            from frontend.state.market_state import MarketState
            from src.portfolio_advisor import generate_portfolio_advice

            market_state = await self.get_state(MarketState)
            advice = await asyncio.to_thread(
                generate_portfolio_advice,
                self.analysis_result,
                market_context=market_state.market_context or None,
                include_news=False,
            )
            if advice:
                self.ai_advice = advice
            else:
                self.error_msg = "アドバイスの生成に失敗しました"
        except Exception as e:
            self.error_msg = f"AI分析エラー: {e}"
        finally:
            self.is_generating_advice = False
            yield

    def new_portfolio(self):
        """新しいポートフォリオを開始"""
        self.holdings = []
        self.current_portfolio_name = "新規ポートフォリオ"
        self.analysis_result = {}
        self.provenance = []
        self.analysis_warnings = []
        self.ai_advice = ""
        self.submode = "input"


def get_active_storage_type() -> str:
    """Read the shared storage setting used by all personal-data stores."""

    from src.settings_storage import get_storage_type

    value = get_storage_type()
    return value if value in {"local", "supabase"} else "local"


def storage_type_label(value: str) -> str:
    return {"local": "ローカルJSON", "supabase": "Supabase"}.get(value, value)


def _personal_data_route_enabled() -> bool:
    from src.app_mode import personal_data_enabled

    return personal_data_enabled()
