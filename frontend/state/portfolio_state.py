import asyncio
from typing import Any

import reflex as rx
from pydantic import BaseModel

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
    ai_advice: str = ""

    # UI状態
    is_loading: bool = False
    is_analyzing: bool = False
    is_generating_advice: bool = False
    error_msg: str = ""
    success_msg: str = ""
    submode: str = "input"  # "input" or "analysis"

    # ストレージタイプ（Streamlit依存を回避するため直接管理）
    storage_type: str = "local"

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

    async def load_portfolio_list(self):
        """保存済みポートフォリオ一覧を取得"""
        try:
            from src.portfolio_storage import list_portfolios

            names = await asyncio.to_thread(list_portfolios, self.storage_type)
            self.portfolio_names = names
        except Exception as e:
            self.error_msg = f"ポートフォリオ一覧の取得に失敗: {e}"

    async def select_portfolio(self, name: str):
        """既存ポートフォリオを選択して読み込む"""
        self.is_loading = True
        self.error_msg = ""
        yield

        try:
            from src.portfolio_storage import load_portfolio

            data = await asyncio.to_thread(load_portfolio, name, self.storage_type)
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
            from src.portfolio_storage import save_portfolio

            holdings_data = holdings_to_payload(self.holdings)
            if not holdings_data:
                self.error_msg = "保存できる保有銘柄がありません"
                return
            success = await asyncio.to_thread(
                save_portfolio, name, holdings_data, self.storage_type
            )
            if success:
                self.current_portfolio_name = name
                self.success_msg = f"「{name}」を保存しました"
                # リストを更新
                from src.portfolio_storage import list_portfolios

                self.portfolio_names = await asyncio.to_thread(
                    list_portfolios, self.storage_type
                )
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
            from src.portfolio_storage import delete_portfolio

            await asyncio.to_thread(
                delete_portfolio, self.current_portfolio_name, self.storage_type
            )
            self.holdings = []
            self.current_portfolio_name = "新規ポートフォリオ"
            self.success_msg = "ポートフォリオを削除しました"
            from src.portfolio_storage import list_portfolios

            self.portfolio_names = await asyncio.to_thread(
                list_portfolios, self.storage_type
            )
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
            from src.portfolio_advisor import generate_portfolio_advice

            advice = await asyncio.to_thread(
                generate_portfolio_advice, self.analysis_result
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
        self.ai_advice = ""
        self.submode = "input"
