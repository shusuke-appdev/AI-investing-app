"""Separate reviewed non-disclosure from missing research; never fill missing values."""

from datetime import date

from src.research.financial_history import PROFILE_METRICS

AUDIT_METRICS = {
    "general": PROFILE_METRICS["general"] + ["fcff_definition"],
    "financial": PROFILE_METRICS["financial"] + ["common_ownership"],
    "reit": PROFILE_METRICS["reit"]
    + [
        "core_ffo",
        "net_income",
        "distributions",
        "reit_reconciliation",
        "denominator_definition",
    ],
}
DOCUMENT_CHECKS = {
    "fcff_definition",
    "common_ownership",
    "reit_reconciliation",
    "denominator_definition",
}


def audit_ticker(evidence, ticker: str) -> dict:
    history = next(
        (h for h in evidence.financial_histories if h.ticker == ticker), None
    )
    review = next((r for r in evidence.accounting_reviews if r.ticker == ticker), None)
    if history is None:
        return {
            "status": "incomplete",
            "ticker": ticker,
            "unexamined": ["財務期間・原資料台帳が未入力"],
            "items": [],
        }
    periods = (
        [(p["kind"], date.fromisoformat(p["end"])) for p in history.expected_periods]
        if history.expected_periods
        else [("annual", end) for end in history.expected_annual_ends]
        + [("interim", history.latest_interim_end)]
    )
    items, missing = [], []
    for kind, end in periods:
        for metric in AUDIT_METRICS[history.profile]:
            fact = next(
                (
                    f
                    for f in history.facts
                    if f.metric == metric
                    and f.period_type == kind
                    and f.period_end == end
                    and f.consolidation == history.reporting_scope
                ),
                None,
            )
            item = next(
                (
                    r
                    for r in (review.items if review else [])
                    if r.metric == metric
                    and r.period_end == end
                    and r.period_type in {kind, None}
                ),
                None,
            )
            state = (
                "verified"
                if fact
                else item.state
                if item and (item.state != "verified" or metric in DOCUMENT_CHECKS)
                else "unexamined"
            )
            row = {
                "metric": metric,
                "period_type": kind,
                "period_end": end.isoformat() if end else None,
                "state": state,
                "reason": fact.definition
                if fact
                else item.reason
                if item
                else "未調査・未照合",
                "source_ids": fact.source_ids
                if fact
                else item.source_ids
                if item
                else [],
            }
            items.append(row)
            if state == "unexamined":
                missing.append(f"{kind} {end} {metric}")
        ledgers = [
            ledger
            for ledger in evidence.segment_ledgers
            if ledger.ticker == ticker
            and ledger.period_end == end
            and ledger.axis == "operating_segments"
        ]
        if not ledgers:
            missing.append(f"{kind} {end} 全報告セグメント・調整消去")
    if review is None:
        missing.append("会計基準・普通株帰属範囲・訂正確認")
    elif review.amendments_status != "checked":
        missing.append("原資料の版・訂正公表一覧の確認")
    return {
        "status": "complete" if not missing else "incomplete",
        "ticker": ticker,
        "profile": history.profile,
        "items": items,
        "unexamined": missing,
        "reviewed_exceptions": [
            i for i in items if i["state"] not in {"verified", "unexamined"}
        ],
        "note": "照合完了と算定可能は別。非開示・適用対象外を0へ変換しません。",
    }


def migration_audit(evidence) -> dict:
    tickers = ["AAPL", "7203.T", "JPM", "8306.T", "PLD", "8951.T"]
    issuers = [audit_ticker(evidence, t) for t in tickers]
    examples = {
        method: [
            v.ticker
            for v in evidence.valuations
            if v.method == method and v.calculate().get("status") == "available"
        ]
        for method in ["fcff_dcf", "sotp", "residual_income", "reit_multiple"]
    }
    return {
        "status": "complete"
        if all(i["status"] == "complete" for i in issuers) and all(examples.values())
        else "incomplete",
        "issuers": issuers,
        "real_calculation_examples": examples,
        "warning": "スキーマは出典の真実性を保証しません。原表の実読と画面・操作の受入確認も必要。",
    }
