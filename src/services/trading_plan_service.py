"""Trading-plan models, validation, risk math, and review metrics."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from statistics import mean
from typing import Any

import pandas as pd


@dataclass
class StopTier:
    """One scale-out stop."""

    label: str
    price: float
    exit_percent: float
    note: str = ""


@dataclass
class JournalEntry:
    """One dated trading-plan note."""

    created_at: str
    kind: str
    note: str


@dataclass
class TradePlanRecord:
    """Persisted manual execution plan."""

    ticker: str
    market_type: str
    entry_date: str
    entry_price: float
    shares: float
    account_value: float
    risk_percent: float
    final_stop_price: float
    status: str = "draft"
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    setup_snapshot: dict[str, Any] = field(default_factory=dict)
    market_snapshot: dict[str, Any] = field(default_factory=dict)
    stops: list[StopTier] = field(default_factory=list)
    t1_status: str = "pending"
    t3_status: str = "pending"
    exit_price: float | None = None
    realized_r: float | None = None
    exit_reason: str = ""
    mistake_tags: list[str] = field(default_factory=list)
    journal: list[JournalEntry] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> TradePlanRecord:
        return cls(
            plan_id=str(value.get("plan_id") or uuid.uuid4()),
            ticker=str(value.get("ticker") or "").upper(),
            market_type=str(value.get("market_type") or "US"),
            entry_date=str(value.get("entry_date") or date.today().isoformat()),
            entry_price=float(value.get("entry_price") or 0.0),
            shares=float(value.get("shares") or 0.0),
            account_value=float(value.get("account_value") or 0.0),
            risk_percent=float(value.get("risk_percent") or 0.5),
            final_stop_price=float(value.get("final_stop_price") or 0.0),
            status=str(value.get("status") or "draft"),
            setup_snapshot=dict(value.get("setup_snapshot") or {}),
            market_snapshot=dict(value.get("market_snapshot") or {}),
            stops=[
                StopTier(
                    label=str(item.get("label") or ""),
                    price=float(item.get("price") or 0.0),
                    exit_percent=float(item.get("exit_percent") or 0.0),
                    note=str(item.get("note") or ""),
                )
                for item in value.get("stops", [])
                if isinstance(item, dict)
            ],
            t1_status=str(value.get("t1_status") or "pending"),
            t3_status=str(value.get("t3_status") or "pending"),
            exit_price=_optional_float(value.get("exit_price")),
            realized_r=_optional_float(value.get("realized_r")),
            exit_reason=str(value.get("exit_reason") or ""),
            mistake_tags=list(value.get("mistake_tags") or []),
            journal=[
                JournalEntry(
                    created_at=str(item.get("created_at") or ""),
                    kind=str(item.get("kind") or "note"),
                    note=str(item.get("note") or ""),
                )
                for item in value.get("journal", [])
                if isinstance(item, dict)
            ],
            created_at=str(value.get("created_at") or datetime.now().isoformat()),
            updated_at=str(value.get("updated_at") or datetime.now().isoformat()),
        )


def build_trade_plan(
    *,
    ticker: str,
    entry_date: str,
    entry_price: float,
    final_stop_price: float,
    account_value: float,
    risk_percent: float = 0.5,
    shares: float | None = None,
    setup_snapshot: dict[str, Any] | None = None,
) -> TradePlanRecord:
    """Validate inputs and create a default three-stop plan."""

    if not ticker.strip():
        raise ValueError("ティッカーを入力してください。")
    if entry_price <= 0 or final_stop_price <= 0:
        raise ValueError("Entry価格と最終ストップは0より大きい必要があります。")
    if final_stop_price >= entry_price:
        raise ValueError("最終ストップはEntry価格より下に設定してください。")
    if account_value <= 0 or risk_percent <= 0:
        raise ValueError("口座金額と許容リスク率は0より大きい必要があります。")

    suggested = suggested_shares(
        account_value, risk_percent, entry_price, final_stop_price
    )
    actual_shares = float(shares) if shares and shares > 0 else suggested
    record = TradePlanRecord(
        ticker=ticker.strip().upper(),
        market_type="JP" if ticker.strip().upper().endswith(".T") else "US",
        entry_date=entry_date or date.today().isoformat(),
        entry_price=entry_price,
        shares=actual_shares,
        account_value=account_value,
        risk_percent=risk_percent,
        final_stop_price=final_stop_price,
        setup_snapshot=dict(setup_snapshot or {}),
        stops=[
            StopTier("Stop 1 / Break-Even", entry_price, 33.0, "確認失敗時に33%縮小"),
            StopTier(
                "Stop 2 / Violation",
                final_stop_price,
                33.0,
                "主要サポート違反時に33%縮小",
            ),
            StopTier(
                "Stop 3 / Final", final_stop_price, 34.0, "最終ストップで残りを退出"
            ),
        ],
    )
    record.journal.append(
        JournalEntry(
            created_at=record.created_at,
            kind="created",
            note=f"Trading plan created. Suggested shares: {suggested:.2f}",
        )
    )
    return record


def suggested_shares(
    account_value: float,
    risk_percent: float,
    entry_price: float,
    final_stop_price: float,
) -> float:
    risk_per_share = entry_price - final_stop_price
    if risk_per_share <= 0:
        return 0.0
    return max(account_value * risk_percent / 100 / risk_per_share, 0.0)


def composite_loss_r(plan: TradePlanRecord) -> float:
    """Return planned loss in R after scale-outs."""

    risk = plan.entry_price - plan.final_stop_price
    if risk <= 0:
        return 0.0
    return round(
        sum(
            ((tier.price - plan.entry_price) / risk) * (tier.exit_percent / 100)
            for tier in plan.stops
        ),
        3,
    )


def active_entry_limit_exceeded(
    plans: list[TradePlanRecord], entry_date: str, *, exclude_id: str = ""
) -> bool:
    active = [
        plan
        for plan in plans
        if plan.plan_id != exclude_id
        and plan.entry_date == entry_date
        and plan.status in {"planned", "active"}
    ]
    return len(active) >= 3


def review_metrics(plans: list[TradePlanRecord]) -> dict[str, Any]:
    closed = [
        plan
        for plan in plans
        if plan.status == "closed" and plan.realized_r is not None
    ]
    wins = [float(plan.realized_r) for plan in closed if float(plan.realized_r) > 0]
    losses = [float(plan.realized_r) for plan in closed if float(plan.realized_r) <= 0]
    avg_win = mean(wins) if wins else 0.0
    avg_loss = mean(losses) if losses else 0.0
    win_rate = len(wins) / len(closed) if closed else 0.0
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss
    best_win = max(wins) if wins else 0.0
    absorb = best_win / abs(avg_loss) if avg_loss < 0 else 0.0
    return {
        "closed_count": len(closed),
        "win_rate": round(win_rate * 100, 1),
        "avg_win_r": round(avg_win, 2),
        "avg_loss_r": round(avg_loss, 2),
        "expectancy_r": round(expectancy, 2),
        "best_win_r": round(best_win, 2),
        "losses_absorbed": round(absorb, 1),
        "rule_adherence": _rule_adherence(closed),
        "mistake_counts": _mistake_counts(closed),
    }


def display_plan(plan: TradePlanRecord) -> dict[str, Any]:
    setup = plan.setup_snapshot
    profit_levels = setup.get("profit_extension_levels") or {}
    return {
        **plan.to_dict(),
        "entry_display": f"{plan.entry_price:,.2f}",
        "shares_display": f"{plan.shares:,.2f}",
        "risk_display": f"{plan.risk_percent:.2f}%",
        "one_r_display": f"{plan.entry_price - plan.final_stop_price:,.2f}",
        "composite_loss_display": f"{composite_loss_r(plan):+.2f}R",
        "grade": str(setup.get("grade") or "N/A"),
        "setup_status": str(setup.get("status") or "N/A"),
        "setup_score_display": str(setup.get("score_display") or "N/A"),
        "stops_display": "\n".join(
            f"- {tier.label}: {tier.price:,.2f} / {tier.exit_percent:.0f}%"
            for tier in plan.stops
        ),
        "profit_levels_display": " / ".join(
            f"{multiple}: {float(profit_levels[multiple]):,.2f}"
            for multiple in ("4x", "6x", "8x", "10x")
            if profit_levels.get(multiple) is not None
        )
        or "N/A",
        "session_stage": _stored_confirmation_stage(plan),
    }


def _stored_confirmation_stage(plan: TradePlanRecord) -> str:
    """Return the persisted review stage without network work during rendering."""

    if plan.t3_status == "confirmed":
        return "T+3"
    if plan.t1_status == "confirmed":
        return "T+1"
    return "T"


def confirmation_stage(entry_date: str, price_df: pd.DataFrame | None) -> str:
    """Return T/T+1/T+3 stage from available daily sessions."""

    if price_df is None or price_df.empty:
        return "unavailable"
    try:
        entry = pd.Timestamp(entry_date).normalize()
        sessions = pd.DatetimeIndex(price_df.index).tz_localize(None).normalize()
    except (TypeError, ValueError):
        return "unavailable"
    completed = int((sessions > entry).sum())
    if completed >= 3:
        return "T+3"
    if completed >= 1:
        return "T+1"
    return "T"


def _rule_adherence(plans: list[TradePlanRecord]) -> float:
    if not plans:
        return 0.0
    adhered = sum(1 for plan in plans if not plan.mistake_tags)
    return round(adhered / len(plans) * 100, 1)


def _mistake_counts(plans: list[TradePlanRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for plan in plans:
        for tag in plan.mistake_tags:
            counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
