"""Strict JSON research snapshots shared by the report and dashboard."""

from __future__ import annotations

import dataclasses
import math
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel


def plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return plain(dataclasses.asdict(value))
    if isinstance(value, BaseModel):
        return plain(value.model_dump())
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, Enum):
        return plain(value.value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        return plain(value.item())
    raise TypeError(f"Unsupported research value: {type(value).__name__}")


def new_bundle(workflow: str, inputs: dict, sections: dict) -> dict:
    outcomes = []
    for key, packet in sections.items():
        if key in {"themes", "policy", "policies"}:
            continue  # Derived output cannot make a failed acquisition successful.
        outcomes.extend(packet.values() if key == "markets" else [packet])
    failed = sum(isinstance(p, dict) and bool(p.get("error_type")) for p in outcomes)
    return {
        "schema_version": 3,
        "engine_version": "codex-research-v3",
        "run_id": str(uuid4()),
        "workflow": workflow,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_at_meaning": "report creation time, not provider observation time",
        "research_only": True,
        "execution_status": "failed"
        if outcomes and failed == len(outcomes)
        else "partial"
        if failed
        else "completed",
        "execution_status_meaning": "workflow execution only; not evidence completeness or investment readiness",
        "inputs": inputs,
        "sections": plain(sections),
        "warnings": [
            "公開情報による調査用。売買指示ではありません。",
            "生成時刻と各資料・価格の基準日は異なります。欠損はゼロ補完しません。",
            "一次資料入力はCodexの確認記録であり、Pythonが真実性を保証するものではありません。",
        ],
    }


def validate_bundle(bundle: dict) -> dict:
    """Read v1/v2/v3 without guessing missing observation dates."""
    if not isinstance(bundle, dict) or bundle.get("schema_version") not in {1, 2, 3}:
        raise ValueError("Unsupported research snapshot")
    for key in ("run_id", "workflow", "created_at"):
        if not isinstance(bundle.get(key), str) or not bundle[key]:
            raise ValueError(f"Missing snapshot {key}")
    if not isinstance(bundle.get("inputs"), dict) or not isinstance(
        bundle.get("sections"), dict
    ):
        raise ValueError("Invalid snapshot inputs/sections")
    if bundle["inputs"].get("market") not in {"US", "JP"}:
        raise ValueError("Invalid snapshot market")
    if any(not isinstance(packet, dict) for packet in bundle["sections"].values()):
        raise ValueError("Snapshot sections must be objects")
    for section in ("markets", "themes", "policies", "comparisons"):
        for market, packet in bundle["sections"].get(section, {}).items():
            if market in {"US", "JP"} and not isinstance(packet, dict):
                raise ValueError("Invalid market packet")
    objects = {
        "analysis",
        "ranking",
        "primary_conditions",
        "filings",
        "filing_catalog",
        "filing_valuation",
        "valuation",
    }
    arrays = {
        "data_status",
        "items",
        "candidates",
        "fundamental_pending",
        "sources",
        "claims",
        "annual",
        "series",
        "chart_data",
        "filing_valuations",
        "facts",
        "accounting_reviews",
        "segment_ledgers",
        "reconciliations",
        "derivations",
        "interpretations",
    }

    def check(value: Any, depth: int = 0) -> None:
        if depth > 40:
            raise ValueError("Snapshot nesting limit exceeded")
        if isinstance(value, list):
            for item in value:
                check(item, depth + 1)
        elif isinstance(value, dict):
            if "connected" in value:
                from src.research.connections import validate_connected

                validate_connected(value["connected"])
            if "primary_conditions" in value and isinstance(
                value["primary_conditions"], dict
            ):
                conditions = value["primary_conditions"].get("conditions", [])
                if not isinstance(conditions, list):
                    raise ValueError("Invalid primary conditions")
            for key, item in value.items():
                if item is not None and (
                    (key in objects and not isinstance(item, dict))
                    or (key in arrays and not isinstance(item, list))
                ):
                    raise ValueError("Invalid snapshot field shape")
                if key == "chart_data" and isinstance(item, list):
                    for point in item:
                        if not isinstance(point, dict):
                            raise ValueError("Invalid chart point")
                        if "name" in point:
                            try:
                                date.fromisoformat(point["name"])
                            except (ValueError, TypeError):
                                raise ValueError("Invalid chart date") from None
                        for field in (
                            "price",
                            "volume",
                            "ma10",
                            "ma20",
                            "ma50",
                            "ma200",
                        ):
                            number = point.get(field)
                            if number is not None and (
                                isinstance(number, bool)
                                or not isinstance(number, (int, float))
                                or not math.isfinite(number)
                            ):
                                raise ValueError("Invalid chart value")
                if key == "source_ids" and (
                    not isinstance(item, list)
                    or any(not isinstance(s, str) or not s for s in item)
                ):
                    raise ValueError("Invalid source references")
                if key in {
                    "facts",
                    "accounting_reviews",
                    "segment_ledgers",
                    "reconciliations",
                    "derivations",
                    "interpretations",
                } and any(not isinstance(row, dict) for row in item or []):
                    raise ValueError("Invalid accounting record")
                check(item, depth + 1)

    check(bundle)
    from src.research.quarterly import evaluate_quarters

    def check_quarters(ticker: str, result: dict) -> None:
        if result.get("reviewed_previous"):
            check_quarters(ticker, result["reviewed_previous"])
        checked = evaluate_quarters(
            result.get("quarters", []), result.get("profile", "general")
        )
        if any(r["ticker"] != ticker for r in checked["quarters"]) or any(
            result.get(k) != checked[k]
            for k in (
                "eps_acceleration",
                "revenue_acceleration",
                "margin_expansion",
                "code33",
            )
        ):
            raise ValueError("Financial screening does not reconcile with its quarters")
        if result.get("comparisons", []) != checked["comparisons"]:
            raise ValueError("Quarter comparisons do not reconcile")
        if any(q["review"] == "opened_and_checked" for q in checked["quarters"]):
            from src.research.evidence import ResearchEvidence

            ResearchEvidence.model_validate(
                {
                    "schema_version": 3,
                    "sources": result.get("sources", []),
                    "quarterly_records": [
                        q
                        for q in checked["quarters"]
                        if q["review"] == "opened_and_checked"
                    ],
                }
            )

    for packet in [
        bundle["sections"].get("market", {}),
        *bundle["sections"].get("markets", {}).values(),
    ]:
        analysis = packet.get("analysis", {})
        if "topdown" in analysis:
            from src.research.topdown_contract import validate_topdown

            validate_topdown(analysis["topdown"])
        for ticker, result in analysis.get("quarterly_fundamentals", {}).items():
            check_quarters(ticker, result)
    if bundle["inputs"].get("evidence") is not None:
        from src.research.evidence import ResearchEvidence

        ResearchEvidence.model_validate(bundle["inputs"]["evidence"])
    for ticker, packet in bundle["sections"].items():
        if "quarterly_fundamentals" in packet:
            check_quarters(ticker, packet["quarterly_fundamentals"])
        filings = packet.get("filings")
        if not filings or not filings.get("financial_history", {}).get("facts"):
            continue
        from src.research.evidence import ResearchEvidence
        from src.research.financial_history import FinancialFact, FinancialHistory

        # completeness() adds display-only status fields; reconstruct input fields.
        history = {
            k: v
            for k, v in filings["financial_history"].items()
            if k in FinancialHistory.model_fields
        }
        history.setdefault("ticker", ticker)
        history.setdefault("currency", history["facts"][0]["currency"])
        history["facts"] = [
            {k: v for k, v in fact.items() if k in FinancialFact.model_fields}
            for fact in history["facts"]
        ]
        if history.get("ticker") != ticker:
            raise ValueError("Snapshot financial issuer mismatch")
        ResearchEvidence.model_validate(
            {
                "schema_version": 2 if filings.get("accounting_reviews") else 1,
                "sources": filings.get("sources", []),
                "claims": filings.get("claims", []),
                "financial_histories": [history],
                "accounting_reviews": filings.get("accounting_reviews", []),
                "segment_ledgers": filings.get("segment_ledgers", []),
                "derivations": filings.get("derivations", []),
            }
        )
    # Strict serialization rejects hostile NaN/Infinity in saved files.
    import json

    json.dumps(bundle, allow_nan=False)
    return bundle
