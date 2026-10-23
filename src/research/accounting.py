"""Source-linked accounting reviews, segment reconciliations and Codex interpretation."""

from __future__ import annotations

import math
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.research.valuation import Quantity


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str = Field(min_length=1)
    period_end: date
    period_type: Literal["annual", "interim", "fiscal_half", "ttm"] | None = None
    state: Literal["verified", "not_disclosed", "not_applicable", "unavailable"]
    reason: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


class Reconciliation(BaseModel):
    """Original signed adjustments, in the stated base currency, not just a label."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    metric: str = Field(min_length=1)
    period_end: date
    period_start: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source_ids: list[str] = Field(min_length=1)
    terms: dict[str, float] = Field(min_length=1)
    result: float
    rounding_tolerance: float = Field(default=0, ge=0)
    definition: str = Field(min_length=1)
    locator: str = Field(min_length=1)

    @field_validator("terms", mode="before")
    @classmethod
    def numeric_terms(cls, value):
        if not isinstance(value, dict) or any(
            isinstance(n, bool) or not isinstance(n, (int, float))
            for n in value.values()
        ):
            raise ValueError("Adjustments must be signed financial numbers")
        return value

    @field_validator("result", "rounding_tolerance", mode="before")
    @classmethod
    def numeric_result(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Adjustments require numeric results and tolerances")
        return value

    @model_validator(mode="after")
    def check_sum(self):
        if self.period_start >= self.period_end or self.period_end > date.today():
            raise ValueError("Invalid adjustment period")
        if not math.isclose(
            sum(self.terms.values()),
            self.result,
            rel_tol=1e-9,
            abs_tol=self.rounding_tolerance,
        ):
            raise ValueError("Original adjustments do not reconcile")
        return self


class AccountingReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    profile: Literal["general", "financial", "reit"]
    latest_check_on: date
    accounting_basis: str = Field(min_length=1)
    ownership_basis: str = Field(min_length=1)
    amendments: str = Field(min_length=1)
    amendments_status: Literal["unexamined", "checked"] = "unexamined"
    items: list[ReviewItem] = Field(min_length=1)
    reconciliations: list[Reconciliation] = Field(default_factory=list)
    amendment_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent(self):
        if self.amendments_status == "checked" and not self.amendment_source_ids:
            raise ValueError("Amendment check requires reviewed source references")
        if self.latest_check_on > date.today() or any(
            i.period_end > self.latest_check_on for i in self.items
        ):
            raise ValueError("Review dates are inconsistent")
        keys = [(i.metric, i.period_type, i.period_end) for i in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate accounting review item")
        return self


class SegmentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    quantity: Quantity
    ownership_basis: str = Field(min_length=1)
    note: str = Field(min_length=1)


class SegmentLedger(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ticker: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    period_end: date
    period_start: date
    axis: Literal["operating_segments", "geography", "products"]
    reported_segments: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    records: list[SegmentRecord] = Field(min_length=1)
    consolidated_total: Quantity
    elimination: Quantity
    rounding_tolerance: float = Field(default=0, ge=0)
    reconciliation_note: str = Field(min_length=1)

    @field_validator("rounding_tolerance", mode="before")
    @classmethod
    def numeric_tolerance(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Segment tolerance must be a number")
        return value

    @model_validator(mode="after")
    def reconcile(self):
        names = [r.name for r in self.records]
        if (
            len(set(names)) != len(names)
            or len(set(self.reported_segments)) != len(self.reported_segments)
            or set(names) != set(self.reported_segments)
        ):
            raise ValueError("All reported segments required exactly once")
        if len({r.metric_name for r in self.records}) != 1:
            raise ValueError("Segment total requires one comparable metric")
        quantities = [r.quantity for r in self.records] + [
            self.consolidated_total,
            self.elimination,
        ]
        if any(
            q.unit != "currency"
            or q.period_end != self.period_end
            or q.period_start != self.period_start
            for q in quantities
        ):
            raise ValueError("Segment periods and currency quantities must match")
        total = sum(r.quantity.value for r in self.records) + self.elimination.value
        if not math.isclose(
            total,
            self.consolidated_total.value,
            rel_tol=1e-9,
            abs_tol=self.rounding_tolerance,
        ):
            raise ValueError("Segments do not reconcile with consolidated total")
        return self


class Interpretation(BaseModel):
    """Agent-authored explanation; never executable instructions or scoring input."""

    model_config = ConfigDict(extra="forbid")
    scope: str = Field(min_length=1)
    kind: Literal["market", "theme", "stock", "deep_dive"]
    run_id: str = Field(min_length=1)
    observations: list[str] = Field(min_length=1)
    company_outlook: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    counterevidence: list[str] = Field(min_length=1)
    missing: list[str] = Field(default_factory=list)
    input_paths: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    author: Literal["Codex"] = "Codex"


class DerivationTerm(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    metric: str = Field(min_length=1)
    quantity: Quantity
    coefficient: float
    rationale: str = Field(min_length=1)

    @field_validator("coefficient", mode="before")
    @classmethod
    def numeric(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Coefficient must be a number, not text or boolean")
        return value


class DerivedQuantity(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ticker: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    metric: str = Field(min_length=1)
    output: Quantity
    kind: Literal["flow_adjustment", "capitalized_flow"] = "flow_adjustment"
    terms: list[DerivationTerm] = Field(min_length=1)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def calculation(self):
        total = sum(t.quantity.value * t.coefficient for t in self.terms)
        if not math.isfinite(total) or not math.isclose(
            total, self.output.value, rel_tol=1e-9, abs_tol=1e-6
        ):
            raise ValueError(
                "Derived value does not reconcile with original quantities"
            )
        if self.kind == "capitalized_flow":
            coherent = (
                self.output.period_start is None
                and all(
                    t.quantity.unit == self.output.unit == "currency"
                    and t.quantity.period_end == self.output.period_end
                    and t.quantity.period_start is not None
                    and 330
                    <= (t.quantity.period_end - t.quantity.period_start).days
                    <= 380
                    for t in self.terms
                )
                and len({t.quantity.period_start for t in self.terms}) == 1
            )
        else:
            coherent = all(
                (t.quantity.period_start, t.quantity.period_end, t.quantity.unit)
                == (self.output.period_start, self.output.period_end, self.output.unit)
                for t in self.terms
            )
        if not coherent:
            raise ValueError("Derived quantities cannot mix periods or units")
        if set(self.output.source_ids) != {
            s for t in self.terms for s in t.quantity.source_ids
        }:
            raise ValueError("Derived source union mismatch")
        return self
