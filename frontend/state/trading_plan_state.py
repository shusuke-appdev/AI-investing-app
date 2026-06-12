import asyncio
from datetime import date, datetime
from typing import Any

import reflex as rx

from src.services.trading_plan_service import (
    JournalEntry,
    TradePlanRecord,
    active_entry_limit_exceeded,
    build_trade_plan,
    display_plan,
    review_metrics,
)


class TradingPlanState(rx.State):
    """State for manual trading-plan execution and review."""

    plans: list[dict[str, Any]] = []
    review: dict[str, Any] = {}
    is_loading: bool = False
    error_msg: str = ""
    success_msg: str = ""

    ticker: str = ""
    entry_date: str = date.today().isoformat()
    entry_price: str = ""
    final_stop_price: str = ""
    account_value: str = "100000"
    risk_percent: str = "0.5"
    shares: str = ""
    realized_r: str = ""
    journal_note: str = ""
    mistake_tag: str = ""

    def set_ticker(self, value: str):
        self.ticker = value.upper()

    def set_entry_date(self, value: str):
        self.entry_date = value

    def set_entry_price(self, value: str):
        self.entry_price = value

    def set_final_stop_price(self, value: str):
        self.final_stop_price = value

    def set_account_value(self, value: str):
        self.account_value = value

    def set_risk_percent(self, value: str):
        self.risk_percent = value

    def set_shares(self, value: str):
        self.shares = value

    def set_realized_r(self, value: str):
        self.realized_r = value

    def set_journal_note(self, value: str):
        self.journal_note = value

    def set_mistake_tag(self, value: str):
        self.mistake_tag = value

    async def load_plans(self):
        self.is_loading = True
        self.error_msg = ""
        yield
        try:
            from src.trading_plan_storage import load_trade_plans

            records = await asyncio.to_thread(load_trade_plans)
            self._assign(records)
        except Exception as exc:
            self.error_msg = f"Trading Planの読み込みに失敗しました: {exc}"
        finally:
            self.is_loading = False
            yield

    async def create_plan(self):
        self.is_loading = True
        self.error_msg = ""
        self.success_msg = ""
        yield
        try:
            from src.services.stock_dashboard_service import (
                build_stock_dashboard_context,
            )
            from src.trading_plan_storage import save_trade_plan

            dashboard = await asyncio.to_thread(
                build_stock_dashboard_context, self.ticker
            )
            plan = build_trade_plan(
                ticker=self.ticker,
                entry_date=self.entry_date,
                entry_price=float(self.entry_price),
                final_stop_price=float(self.final_stop_price),
                account_value=float(self.account_value),
                risk_percent=float(self.risk_percent),
                shares=float(self.shares) if self.shares else None,
                setup_snapshot=dashboard.trade_setup,
            )
            if not await asyncio.to_thread(save_trade_plan, plan):
                raise ValueError("Trading Planの保存に失敗しました。")
            self.success_msg = f"{plan.ticker} のTrading Planを作成しました。"
            self.ticker = ""
            self.entry_price = ""
            self.final_stop_price = ""
            self.shares = ""
            from src.trading_plan_storage import load_trade_plans

            self._assign(await asyncio.to_thread(load_trade_plans))
        except Exception as exc:
            self.error_msg = f"Trading Planの作成に失敗しました: {exc}"
        finally:
            self.is_loading = False
            yield

    async def activate_plan(self, plan_id: str):
        await self._set_status(plan_id, "active")

    async def close_plan(self, plan_id: str):
        await self._close_plan(plan_id)

    async def cancel_plan(self, plan_id: str):
        await self._set_status(plan_id, "cancelled")

    async def mark_t1_confirmed(self, plan_id: str):
        await self._set_checkpoint(plan_id, "t1_status", "confirmed")

    async def mark_t3_confirmed(self, plan_id: str):
        await self._set_checkpoint(plan_id, "t3_status", "confirmed")

    async def add_journal_note(self, plan_id: str):
        self.error_msg = ""
        try:
            if not self.journal_note.strip():
                raise ValueError("ジャーナルメモを入力してください。")
            from src.trading_plan_storage import (
                get_trade_plan,
                load_trade_plans,
                save_trade_plan,
            )

            plan = await asyncio.to_thread(get_trade_plan, plan_id)
            if plan is None:
                raise ValueError("対象のTrading Planがありません。")
            plan.journal.append(
                JournalEntry(
                    created_at=datetime.now().isoformat(),
                    kind="note",
                    note=self.journal_note.strip(),
                )
            )
            if (
                self.mistake_tag.strip()
                and self.mistake_tag.strip() not in plan.mistake_tags
            ):
                plan.mistake_tags.append(self.mistake_tag.strip())
            plan.updated_at = datetime.now().isoformat()
            if not await asyncio.to_thread(save_trade_plan, plan):
                raise ValueError("Trading Planの保存に失敗しました。")
            self.journal_note = ""
            self.mistake_tag = ""
            self._assign(await asyncio.to_thread(load_trade_plans))
        except Exception as exc:
            self.error_msg = f"ジャーナル更新に失敗しました: {exc}"

    async def delete_plan(self, plan_id: str):
        self.error_msg = ""
        try:
            from src.trading_plan_storage import delete_trade_plan, load_trade_plans

            if not await asyncio.to_thread(delete_trade_plan, plan_id):
                raise ValueError("削除対象が存在しないか、削除に失敗しました。")
            self._assign(await asyncio.to_thread(load_trade_plans))
            self.success_msg = "Trading Planを削除しました。"
        except Exception as exc:
            self.error_msg = f"削除に失敗しました: {exc}"

    async def _set_status(self, plan_id: str, status: str):
        self.error_msg = ""
        try:
            from src.trading_plan_storage import (
                get_trade_plan,
                load_trade_plans,
                save_trade_plan,
            )

            plan = await asyncio.to_thread(get_trade_plan, plan_id)
            if plan is None:
                raise ValueError("対象のTrading Planがありません。")
            records = await asyncio.to_thread(load_trade_plans)
            if status == "active" and active_entry_limit_exceeded(
                records, plan.entry_date, exclude_id=plan.plan_id
            ):
                raise ValueError("同一Entry日の新規ポジションは最大3件です。")
            plan.status = status
            plan.updated_at = datetime.now().isoformat()
            if not await asyncio.to_thread(save_trade_plan, plan):
                raise ValueError("Trading Planの保存に失敗しました。")
            self._assign(await asyncio.to_thread(load_trade_plans))
            self.success_msg = f"{plan.ticker} を {status} に更新しました。"
        except Exception as exc:
            self.error_msg = f"状態更新に失敗しました: {exc}"

    async def _set_checkpoint(self, plan_id: str, field_name: str, value: str):
        self.error_msg = ""
        try:
            from src.trading_plan_storage import (
                get_trade_plan,
                load_trade_plans,
                save_trade_plan,
            )

            plan = await asyncio.to_thread(get_trade_plan, plan_id)
            if plan is None:
                raise ValueError("対象のTrading Planがありません。")
            setattr(plan, field_name, value)
            plan.updated_at = datetime.now().isoformat()
            if not await asyncio.to_thread(save_trade_plan, plan):
                raise ValueError("Trading Planの保存に失敗しました。")
            self._assign(await asyncio.to_thread(load_trade_plans))
        except Exception as exc:
            self.error_msg = f"確認状態の更新に失敗しました: {exc}"

    async def _close_plan(self, plan_id: str):
        self.error_msg = ""
        try:
            from src.trading_plan_storage import (
                get_trade_plan,
                load_trade_plans,
                save_trade_plan,
            )

            plan = await asyncio.to_thread(get_trade_plan, plan_id)
            if plan is None:
                raise ValueError("対象のTrading Planがありません。")
            plan.status = "closed"
            plan.realized_r = float(self.realized_r) if self.realized_r else None
            if self.journal_note.strip():
                plan.journal.append(
                    JournalEntry(
                        created_at=datetime.now().isoformat(),
                        kind="close",
                        note=self.journal_note.strip(),
                    )
                )
            if (
                self.mistake_tag.strip()
                and self.mistake_tag.strip() not in plan.mistake_tags
            ):
                plan.mistake_tags.append(self.mistake_tag.strip())
            plan.updated_at = datetime.now().isoformat()
            if not await asyncio.to_thread(save_trade_plan, plan):
                raise ValueError("Trading Planの保存に失敗しました。")
            self.realized_r = ""
            self.journal_note = ""
            self.mistake_tag = ""
            self._assign(await asyncio.to_thread(load_trade_plans))
        except Exception as exc:
            self.error_msg = f"Close更新に失敗しました: {exc}"

    def _assign(self, records: list[TradePlanRecord]):
        self.plans = [display_plan(plan) for plan in records]
        self.review = review_metrics(records)
