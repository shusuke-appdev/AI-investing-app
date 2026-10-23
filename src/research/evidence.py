"""Validate provenance structure, never claim to verify document truth."""

from __future__ import annotations

from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.research.accounting import (
    AccountingReview,
    DerivedQuantity,
    Interpretation,
    SegmentLedger,
)
from src.research.financial_history import FinancialHistory
from src.research.quarterly import Quarter
from src.research.valuation import ValuationInput


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    url: str
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    published_on: date
    accessed_on: date
    locator: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    kind: Literal["primary", "independent"]
    review: Literal["opened_and_checked", "unverified"]
    document_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Evidence requires a credential-free HTTPS URL")
        return value

    @model_validator(mode="after")
    def valid_dates(self):
        if self.published_on > self.accessed_on or self.accessed_on > date.today():
            raise ValueError("Future or inconsistent evidence dates")
        return self


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    ticker: str
    category: Literal["financial", "segment", "guidance", "catalyst", "risk", "outlook"]
    text: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    period: str = Field(min_length=1)
    currency: str = ""
    unit: str = ""
    value: float | None = None

    @model_validator(mode="after")
    def numeric_units(self):
        if self.value is not None and (not self.unit or not self.currency):
            raise ValueError("Numeric evidence requires explicit currency and unit")
        return self


class ExternalCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    exchange: str
    company_name: str
    theme: str
    business_relationship: str = Field(min_length=1)
    evidence_date: date
    official_domain: str
    security_type: Literal["common_stock"] = "common_stock"
    source_ids: list[str] = Field(min_length=2)


class ResearchEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1, 2, 3] = 1
    sources: list[EvidenceSource] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    external_candidates: list[ExternalCandidate] = Field(
        default_factory=list, max_length=40
    )
    valuations: list[ValuationInput] = Field(default_factory=list)
    financial_histories: list[FinancialHistory] = Field(default_factory=list)
    accounting_reviews: list[AccountingReview] = Field(default_factory=list)
    segment_ledgers: list[SegmentLedger] = Field(default_factory=list)
    derivations: list[DerivedQuantity] = Field(default_factory=list)
    interpretations: list[Interpretation] = Field(default_factory=list)
    # Standalone quarters need neither three annuals nor a valuation model.
    quarterly_records: list[Quarter] = Field(default_factory=list)

    @model_validator(mode="after")
    def linked_sources(self):
        sources = {source.id: source for source in self.sources}
        if self.quarterly_records and self.schema_version != 3:
            raise ValueError("Quarterly evidence requires version 3")
        for record in self.quarterly_records:
            if record.review != "opened_and_checked":
                raise ValueError(
                    "Evidence quarters require actual primary-document review"
                )
            for source_id in record.source_ids:
                source = sources.get(source_id)
                if (
                    source is None
                    or source.ticker != record.ticker
                    or source.kind != "primary"
                    or source.review != "opened_and_checked"
                ):
                    raise ValueError("Quarter source or issuer mismatch")
            if not any(
                sources[key].published_on == record.published_on
                and sources[key].published_on >= record.period_end
                for key in record.source_ids
            ):
                raise ValueError("Quarter publication must match a reviewed statement")
        if len(sources) != len(self.sources):
            raise ValueError("Duplicate source id")
        for claim in self.claims:
            for source_id in claim.source_ids:
                source = sources.get(source_id)
                if source is None or source.ticker != claim.ticker:
                    raise ValueError("Missing source or ticker mismatch")
                if source.review != "opened_and_checked":
                    raise ValueError(
                        "Claims require document review, not URL-only validation"
                    )
        for candidate in self.external_candidates:
            selected = [sources.get(key) for key in candidate.source_ids]
            if any(
                source is None
                or source.ticker != candidate.ticker
                or source.review != "opened_and_checked"
                for source in selected
            ):
                raise ValueError("External candidates need reviewed, matching sources")
            if {source.kind for source in selected} != {"primary", "independent"}:
                raise ValueError(
                    "External candidates need primary and independent evidence"
                )
            if len({urlsplit(source.url).hostname for source in selected}) < 2:
                raise ValueError("Independent evidence requires different publishers")
            if not 0 <= (date.today() - candidate.evidence_date).days <= 548:
                raise ValueError(
                    "External candidate evidence must be recent and not future-dated"
                )
        identities = [
            (
                item.ticker,
                item.method,
                item.reit_metric if item.method == "reit_multiple" else "",
                item.shares.period_end,
            )
            for item in self.valuations
        ]
        if len(set(identities)) != len(identities) or (
            self.schema_version == 1
            and len({item.ticker for item in self.valuations}) != len(self.valuations)
        ):
            raise ValueError("Duplicate valuation identity")

        def checked(ids, ticker, period=None):
            for key in ids:
                s = sources.get(key)
                if (
                    s is None
                    or s.ticker != ticker
                    or s.kind != "primary"
                    or s.review != "opened_and_checked"
                    or (period is not None and s.published_on < period)
                ):
                    raise ValueError(
                        "Accounting needs reviewed, matching primary sources"
                    )

        for review in self.accounting_reviews:
            history = next(
                (h for h in self.financial_histories if h.ticker == review.ticker), None
            )
            if history is None or history.profile != review.profile:
                raise ValueError("Accounting review requires a matching issuer profile")
            checked(review.amendment_source_ids, review.ticker)
            for reconciliation in review.reconciliations:
                checked(
                    reconciliation.source_ids, review.ticker, reconciliation.period_end
                )
                if reconciliation.currency != history.currency:
                    raise ValueError("Adjustment currency mismatch")
                if not any(
                    f.metric == reconciliation.metric
                    and f.period_end == reconciliation.period_end
                    and f.period_start == reconciliation.period_start
                    and abs(f.base_value - reconciliation.result)
                    <= max(1e-6, reconciliation.rounding_tolerance)
                    for f in history.facts
                ):
                    raise ValueError(
                        "Adjustment result does not reconcile to original history"
                    )
            for item in review.items:
                checked(item.source_ids, review.ticker, item.period_end)
        for ledger in self.segment_ledgers:
            checked(ledger.source_ids, ledger.ticker, ledger.period_end)
            for q in [r.quantity for r in ledger.records] + [
                ledger.consolidated_total,
                ledger.elimination,
            ]:
                checked(q.source_ids, ledger.ticker, q.period_end)
        for derivation in self.derivations:
            checked(
                derivation.output.source_ids,
                derivation.ticker,
                derivation.output.period_end,
            )
        for interpretation in self.interpretations:
            for key in interpretation.source_ids:
                if key not in sources or sources[key].review != "opened_and_checked":
                    raise ValueError(
                        "Interpretation cites unreviewed or missing source"
                    )
            if interpretation.company_outlook and not interpretation.source_ids:
                raise ValueError("Company outlook requires reviewed sources")
        for valuation in self.valuations:
            for quantity in valuation.quantities():
                for source_id in quantity.source_ids:
                    source = sources.get(source_id)
                    if (
                        source is None
                        or source.ticker != valuation.ticker
                        or source.kind != "primary"
                        or source.review != "opened_and_checked"
                    ):
                        raise ValueError(
                            "Valuation needs reviewed primary sources for the same ticker"
                        )
                    if source.published_on < quantity.period_end:
                        raise ValueError(
                            "Historical quantity cannot postdate its source publication"
                        )
        if len({item.ticker for item in self.financial_histories}) != len(
            self.financial_histories
        ):
            raise ValueError("One reconciled financial history per ticker")
        for history in self.financial_histories:
            for fact in history.facts:
                for key in fact.source_ids:
                    source = sources.get(key)
                    if (
                        source is None
                        or source.ticker != history.ticker
                        or source.kind != "primary"
                        or source.review != "opened_and_checked"
                        or source.published_on < fact.period_end
                    ):
                        raise ValueError(
                            "Financial facts require reviewed matching primary sources"
                        )
            for valuation in [
                item for item in self.valuations if item.ticker == history.ticker
            ]:
                if valuation.currency != history.currency:
                    raise ValueError("History and valuation currencies differ")
                for metric, quantity in valuation.named_quantities():
                    if self.schema_version == 1 and (
                        metric.startswith("segment:")
                        or metric == "corporate_adjustment"
                    ):
                        continue
                    matches = [
                        fact
                        for fact in history.facts
                        if fact.metric == metric
                        and fact.period_end == quantity.period_end
                        and fact.period_start == quantity.period_start
                        and fact.consolidation == history.reporting_scope
                    ]
                    derivations = [
                        d
                        for d in self.derivations
                        if d.ticker == history.ticker
                        and d.metric == metric
                        and d.currency == valuation.currency
                    ]
                    ledger_matches = [
                        r.quantity
                        for ledger in self.segment_ledgers
                        if ledger.ticker == history.ticker
                        and ledger.currency == valuation.currency
                        and ledger.axis == "operating_segments"
                        for r in ledger.records
                        if metric == f"segment:{r.name}"
                        and r.metric_name
                        == next(
                            (
                                s.metric_name
                                for s in valuation.segments
                                if s.name == r.name
                            ),
                            "",
                        )
                    ]

                    def same(q, quantity=quantity):
                        return (
                            q.unit == quantity.unit
                            and q.period_start == quantity.period_start
                            and q.period_end == quantity.period_end
                            and abs(q.value - quantity.value)
                            <= max(1e-6, abs(quantity.value) * 1e-9)
                            and set(quantity.source_ids).issubset(q.source_ids)
                        )

                    if (
                        not any(
                            (("shares" in fact.unit) == (quantity.unit == "shares"))
                            and abs(fact.base_value - quantity.value)
                            <= max(1e-6, abs(quantity.value) * 1e-9)
                            and set(quantity.source_ids).issubset(fact.source_ids)
                            for fact in matches
                        )
                        and not any(same(d.output) for d in derivations)
                        and not any(same(q) for q in ledger_matches)
                    ):
                        raise ValueError(
                            "Valuation quantity does not reconcile with financial history"
                        )
        if self.schema_version >= 2:
            histories = {h.ticker: h for h in self.financial_histories}
            for derivation in self.derivations:
                history = histories.get(derivation.ticker)
                if history is None or history.currency != derivation.currency:
                    raise ValueError("Derivation requires matching financial history")
                for term in derivation.terms:
                    if not any(
                        f.metric == term.metric
                        and f.consolidation == history.reporting_scope
                        and f.period_start == term.quantity.period_start
                        and f.period_end == term.quantity.period_end
                        and abs(f.base_value - term.quantity.value)
                        <= max(1e-6, abs(term.quantity.value) * 1e-9)
                        and set(term.quantity.source_ids).issubset(f.source_ids)
                        for f in history.facts
                    ):
                        raise ValueError(
                            "Derivation term must reconcile with an original fact"
                        )
            for history in self.financial_histories:
                for fact in history.facts:
                    for component in fact.components:
                        checked(
                            component.source_ids, history.ticker, component.period_end
                        )
                        if not any(
                            f.metric == fact.metric
                            and f.period_type != "ttm"
                            and f.period_start == component.period_start
                            and f.period_end == component.period_end
                            and abs(f.base_value - component.base_value)
                            <= max(1e-6, abs(component.base_value) * 1e-9)
                            and set(component.source_ids).issubset(f.source_ids)
                            for f in history.facts
                        ):
                            raise ValueError(
                                "TTM component requires the original reported fact"
                            )
            for valuation in self.valuations:
                if valuation.ticker not in histories:
                    raise ValueError("Version2 valuation requires a financial history")
                if (
                    valuation.reporting_scope
                    != histories[valuation.ticker].reporting_scope
                ):
                    raise ValueError("Valuation and history reporting scope differ")
                if valuation.method in {"fcff_dcf", "sotp"} and (
                    valuation.noncontrolling_interest is None
                    or valuation.nonoperating_assets is None
                    or not valuation.bridge_rationale
                ):
                    raise ValueError(
                        "Enterprise value requires reviewed NCI/nonoperating asset bridge"
                    )
                if valuation.method == "fcff_dcf" and not valuation.derivation:
                    raise ValueError("Unlevered FCFF derivation must be explained")
                if valuation.method in {"residual_income", "reit_multiple"} and (
                    valuation.ownership_basis == "consolidated"
                    or not valuation.denominator_basis
                ):
                    raise ValueError(
                        "Financial/REIT valuation needs explicit common ownership and denominator basis"
                    )
                if valuation.method == "sotp":
                    if (
                        any(s.value_basis == "equity" for s in valuation.segments)
                        and valuation.debt_scope != "enterprise_segments_only"
                    ):
                        raise ValueError(
                            "Mixed equity/enterprise segments require an enterprise-only debt bridge"
                        )
                    ledgers = [
                        ledger
                        for ledger in self.segment_ledgers
                        if ledger.ticker == valuation.ticker
                        and ledger.axis == "operating_segments"
                        and ledger.period_end == valuation.shares.period_end
                    ]
                    if not ledgers or not any(
                        set(ledger.reported_segments)
                        == set(valuation.all_reported_segments)
                        for ledger in ledgers
                    ):
                        raise ValueError(
                            "SOTP segments must match the primary segment registry"
                        )
        return self

    def discovery(self, market: str, themes: list[str]) -> dict:
        from datetime import datetime, timezone

        from src.services.theme_grounded_research_service import (
            validate_external_discovery,
        )

        source_map = {source.id: source for source in self.sources}
        candidates = []
        for candidate in self.external_candidates:
            item = candidate.model_dump(mode="json", exclude={"source_ids"})
            item["sources"] = [
                {"url": source_map[key].url, "title": source_map[key].title}
                for key in candidate.source_ids
            ]
            candidates.append(item)
        return validate_external_discovery(
            market_type=market,
            themes=themes,
            generated={
                "status": "available" if candidates else "unavailable",
                "model": "Codex evidence",
                "data": {"candidates": candidates},
                "citations": [
                    {"url": source.url, "title": source.title}
                    for source in self.sources
                ],
            },
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def for_ticker(self, ticker: str) -> dict:
        from src.research.accounting_audit import audit_ticker

        claims = [
            claim.model_dump(mode="json")
            for claim in self.claims
            if claim.ticker == ticker
        ]
        has_facts = any(
            h.ticker == ticker and h.facts for h in self.financial_histories
        )
        return {
            "status": "partial" if claims or has_facts else "unavailable",
            "verification": "agent_attested; schema checks do not verify document truth",
            "claims": claims,
            "quarterly_records": [
                r.model_dump(mode="json")
                for r in self.quarterly_records
                if r.ticker == ticker
            ],
            "sources": [
                source.model_dump(mode="json")
                for source in self.sources
                if source.ticker == ticker
            ],
            "missing": self.missing,
            "accounting_audit": audit_ticker(self, ticker),
            "accounting_reviews": [
                r.model_dump(mode="json")
                for r in self.accounting_reviews
                if r.ticker == ticker
            ],
            "segment_ledgers": [
                ledger.model_dump(mode="json")
                for ledger in self.segment_ledgers
                if ledger.ticker == ticker
            ],
            "derivations": [
                d.model_dump(mode="json")
                for d in self.derivations
                if d.ticker == ticker
            ],
            "financial_history": next(
                (
                    history.completeness()
                    for history in self.financial_histories
                    if history.ticker == ticker
                ),
                {
                    "status": "unavailable",
                    "missing": ["3年・最新中間の期間指定と財務確認が未入力"],
                },
            ),
        }
