"""Comparable standalone quarters and transparent, non-recommendation Code33."""

from __future__ import annotations

import math
from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Quarter(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ticker: str
    period_end: date
    period_start: date | None = None
    period_type: Literal["quarter"] = "quarter"
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    revenue: float | None = None
    diluted_eps: float | None = None
    parent_net_income: float | None = None
    accounting_basis: str = Field(min_length=1)
    ownership_basis: Literal["parent_common", "parent", "unconfirmed"] = "unconfirmed"
    consolidation: Literal["consolidated", "standalone", "unconfirmed"] = "unconfirmed"
    scope_basis: str = "provider_scope_unreviewed"
    eps_basis: Literal["diluted", "unconfirmed"] = "diluted"
    split_basis: str = Field(min_length=1)
    source: str
    source_ids: list[str] = Field(default_factory=list)
    accession: str = ""
    published_on: date | None = None
    fetched_at: str = ""
    review: Literal["automatic_unreviewed", "opened_and_checked"] = (
        "automatic_unreviewed"
    )
    derivation: str = ""

    @field_validator("revenue", "diluted_eps", "parent_net_income", mode="before")
    @classmethod
    def numeric(cls, value):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("Quarter values must be finite numbers")
        return value

    @model_validator(mode="after")
    def coherent(self):
        if (
            self.period_end > date.today()
            or self.period_start
            and not 65 <= (self.period_end - self.period_start).days <= 110
        ):
            raise ValueError("Not a standalone quarter")
        if (
            self.published_on
            and not self.period_end <= self.published_on <= date.today()
        ):
            raise ValueError("Invalid publication date")
        url = urlsplit(self.source)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Invalid financial source")
        if self.review == "opened_and_checked" and (
            not self.source_ids
            or not self.period_start
            or not self.published_on
            or self.ownership_basis == "unconfirmed"
            or self.consolidation == "unconfirmed"
        ):
            raise ValueError(
                "Reviewed quarter requires original period and linked sources"
            )
        return self


def evaluate_quarters(records: list[dict], profile: str = "general") -> dict:
    quarters = sorted(
        (Quarter.model_validate(r) for r in records), key=lambda r: r.period_end
    )
    if (
        len({(r.ticker, r.period_end) for r in quarters}) != len(quarters)
        or len({r.ticker for r in quarters}) > 1
    ):
        raise ValueError("Duplicate quarter or mixed issuer")
    base = {
        "method": "EPS・売上前年同期比が直近3四半期とも正で順次上昇、親会社純利益率も正で順次拡大。研究参考。",
        "quarters": [r.model_dump(mode="json") for r in quarters],
        "profile": profile,
        "eps_acceleration": None,
        "revenue_acceleration": None,
        "margin_expansion": None,
        "code33": None,
        "comparisons": [],
        "verification": "一次資料確認済み"
        if quarters and all(q.review == "opened_and_checked" for q in quarters)
        else "自動取得・未照合"
        if quarters
        else "未確認",
        "reason": "直近3四半期と各前年同期の単独四半期データが必要",
    }
    if profile in {"financial", "reit", "unsupported"}:
        return {
            **base,
            "status": "not_applicable",
            "reason": "金融・REIT・対象外証券は一律Code33の対象外。既存の業態別分析を参照。",
        }
    if len(quarters) < 3:
        return {**base, "status": "insufficient_data"}
    recent = quarters[-3:]
    if any(
        not 65 <= (b.period_end - a.period_end).days <= 115
        for a, b in zip(recent, recent[1:], strict=False)
    ):
        return {
            **base,
            "status": "incomparable",
            "reason": "直近3期が連続四半期ではありません",
        }
    needed = []
    for q in recent:
        matches = [
            p for p in quarters if 350 <= (q.period_end - p.period_end).days <= 380
        ]
        if len(matches) != 1:
            return {**base, "status": "insufficient_data"}
        p = matches[0]
        needed.extend((q, p))
        for key in (
            "currency",
            "accounting_basis",
            "ownership_basis",
            "consolidation",
            "scope_basis",
            "eps_basis",
            "split_basis",
        ):
            if getattr(q, key) != getattr(p, key) or getattr(q, key) in {
                "unconfirmed",
                "company_non_gaap",
            }:
                return {
                    **base,
                    "status": "incomparable",
                    "reason": "通貨・会計・帰属・希薄化EPS・分割基準が一致しないか未確認",
                }
        if (
            q.revenue is None
            or p.revenue is None
            or p.revenue <= 0
            or q.diluted_eps is None
            or p.diluted_eps is None
            or q.parent_net_income is None
            or q.revenue <= 0
        ):
            return {
                **base,
                "status": "insufficient_data",
                "reason": "比較に必要な売上・希薄化EPS・親会社利益が不足",
            }
        eps_growth = (
            (q.diluted_eps / p.diluted_eps - 1) * 100 if p.diluted_eps > 0 else None
        )
        base["comparisons"].append(
            {
                "period_end": q.period_end.isoformat(),
                "prior_period_end": p.period_end.isoformat(),
                "eps_growth": eps_growth,
                "revenue_growth": (q.revenue / p.revenue - 1) * 100,
                "net_margin": q.parent_net_income / q.revenue * 100,
                "turnaround": p.diluted_eps <= 0 < q.diluted_eps,
            }
        )
    # Successive quarters must have the same definitions too, not just each YoY pair.
    if any(
        len({getattr(q, k) for q in needed}) > 1
        for k in (
            "currency",
            "accounting_basis",
            "ownership_basis",
            "consolidation",
            "scope_basis",
            "split_basis",
        )
    ):
        return {
            **base,
            "status": "incomparable",
            "reason": "四半期間で会計・帰属・分割基準が変化",
        }

    def accelerating(key):
        values = [r[key] for r in base["comparisons"]]
        if any(v is None for v in values):
            return None
        return all(v > 0 for v in values) and all(
            b > a for a, b in zip(values, values[1:], strict=False)
        )

    conditions = [
        accelerating(k) for k in ("eps_growth", "revenue_growth", "net_margin")
    ]
    base.update(
        eps_acceleration=conditions[0],
        revenue_acceleration=conditions[1],
        margin_expansion=conditions[2],
        code33=None if None in conditions else all(conditions),
        verification="一次資料確認済み"
        if all(q.review == "opened_and_checked" for q in needed)
        else "自動取得・未照合",
        status="available" if None not in conditions else "incomparable",
        reason="前年EPSが0以下。黒字転換を成長率・Code33合格へ変換しません。"
        if None in conditions
        else "各条件は研究用。業績加速は将来の株価上昇を保証しません。",
    )
    return base
