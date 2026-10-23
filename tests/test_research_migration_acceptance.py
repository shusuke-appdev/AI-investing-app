"""Migration acceptance, distinct from issuer-document review and live acquisition."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from src.research.accounting import DerivedQuantity, SegmentLedger
from src.research.bundle import new_bundle, validate_bundle
from src.research.evidence import ResearchEvidence
from src.research.financial_history import FinancialFact
from src.research.runner import refresh, resume
from src.research.valuation import ValuationInput


@pytest.mark.parametrize("bad", [True, "10", float("inf")])
@pytest.mark.parametrize(
    "kind", ["quantity", "fact", "component", "assumption", "multiple", "coefficient"]
)
def test_financial_inputs_reject_wrong_numeric_types(kind, bad):
    from src.research.accounting import DerivationTerm
    from src.research.financial_history import PeriodComponent
    from src.research.valuation import Quantity, Segment

    if kind == "quantity":
        model, data = Quantity, quantity(bad)
    elif kind == "fact":
        model, data = FinancialFact, {**ttm(), "value": bad}
    elif kind == "component":
        model, data = PeriodComponent, {**ttm()["components"][0], "base_value": bad}
    elif kind == "assumption":
        model, data = ValuationInput, {**valuation("residual_income"), "wacc": bad}
    elif kind == "multiple":
        model, data = (
            Segment,
            dict(
                name="A",
                metric=quantity(10),
                metric_name="earnings",
                multiple=bad,
                multiple_rationale="Fixture",
            ),
        )
    else:
        model, data = (
            DerivationTerm,
            dict(
                metric="tax",
                quantity=quantity(10),
                coefficient=bad,
                rationale="Fixture",
            ),
        )
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize("bad", [True, "10", float("inf")])
def test_reconciliation_rejects_type_and_nonfinite(bad):
    from src.research.accounting import Reconciliation

    data = dict(
        metric="ffo",
        period_start="2023-01-01",
        period_end="2023-12-31",
        currency="USD",
        source_ids=["s"],
        terms={"NI": 10},
        result=10,
        definition="Original adjustment",
        locator="p1",
    )
    assert Reconciliation.model_validate(data).result == 10
    data["terms"]["NI"] = bad
    with pytest.raises(ValidationError):
        Reconciliation.model_validate(data)


def test_repeated_refresh_failure_is_not_a_success(monkeypatch):
    from src.services import market_dashboard_service as service
    from src.services.analysis_context import MarketContext

    original = saved()
    original["sections"]["market"]["analysis"]["errors"] = ["Same provider failure"]
    monkeypatch.setattr(
        service,
        "build_market_high_context",
        lambda market, base: MarketContext(
            market_type=market, errors=["Same provider failure"]
        ),
    )
    result = refresh(original, "credit-risk", market_type="US")
    assert result["execution_status"] == "partial"
    assert (
        result["sections"]["market"]["analysis"]
        == original["sections"]["market"]["analysis"]
    )


def test_json_pointer_supports_japanese_ticker_without_changing_decisions():
    original = new_bundle(
        "stock", {"market": "JP"}, {"7203.T": {"analysis": {"decision": False}}}
    )
    payload = dict(
        schema_version=2,
        interpretations=[
            dict(
                scope="7203.T",
                kind="stock",
                run_id=original["run_id"],
                observations=["fixture"],
                counterevidence=["fixture"],
                input_paths=["/sections/7203.T/analysis"],
                author="Codex",
            )
        ],
    )
    result = resume(original, ResearchEvidence.model_validate(payload))
    assert (
        result["sections"]["7203.T"]["analysis"]
        == original["sections"]["7203.T"]["analysis"]
    )
    payload["interpretations"][0]["input_paths"] = ["/sections/other/analysis"]
    with pytest.raises(ValueError, match="missing calculation"):
        resume(original, ResearchEvidence.model_validate(payload))


def test_reverse_dcf_only_inverts_dcf_and_reports_both_dates():
    data = valuation("fcff_dcf")
    data.update(cash=quantity(10), debt=quantity(20), fcff=quantity(100, "fcff"))
    model = ValuationInput.model_validate(data)
    base = model.calculate()["cases"][1]["value"]
    inverted = model.reverse_dcf(base, "2024-05-01")
    assert inverted["status"] == "available"
    assert inverted["implied_growth"] == pytest.approx(model.growth_rate)
    assert inverted["price_observed_on"] == "2024-05-01"
    assert inverted["valuation_period_end"] == "2023-12-31"
    assert model.reverse_dcf(1e12, "2024-05-01")["implied_growth"] is None
    assert model.reverse_dcf(base, None)["status"] == "unavailable"
    other = ValuationInput.model_validate(valuation("residual_income"))
    assert other.reverse_dcf(10, "2024-05-01")["status"] == "unavailable"


def test_reviewed_non_disclosure_not_a_zero_and_verified_requires_fact():
    from src.research.accounting_audit import audit_ticker

    data = evidence([])
    data["accounting_reviews"] = [
        dict(
            ticker="TEST",
            profile="financial",
            latest_check_on="2024-05-01",
            accounting_basis="US-GAAP",
            ownership_basis="common equity",
            amendments="Fixture",
            items=[
                dict(
                    metric="roe",
                    period_end="2024-03-31",
                    period_type="interim",
                    state="not_disclosed",
                    reason="Not reported in this fixture",
                    source_ids=["s"],
                )
            ],
        )
    ]
    audit = audit_ticker(ResearchEvidence.model_validate(data), "TEST")
    item = next(
        i
        for i in audit["items"]
        if i["metric"] == "roe" and i["period_type"] == "interim"
    )
    assert item["state"] == "not_disclosed"
    assert "value" not in item
    assert audit["status"] == "incomplete"
    data["accounting_reviews"][0]["items"][0]["state"] = "verified"
    audit = audit_ticker(ResearchEvidence.model_validate(data), "TEST")
    assert any("roe" in m for m in audit["unexamined"])


def test_derivation_cannot_invent_a_quantity_just_by_citing_a_reviewed_url():
    data = evidence([])
    q = quantity(123)
    data["derivations"] = [
        dict(
            ticker="TEST",
            currency="USD",
            metric="book_equity",
            output=q,
            terms=[
                dict(metric="invented", quantity=q, coefficient=1, rationale="fixture")
            ],
            rationale="fixture",
        )
    ]
    with pytest.raises(ValidationError, match="original fact"):
        ResearchEvidence.model_validate(data)


def source():
    return dict(
        id="s",
        ticker="TEST",
        url="https://example.org/annual",
        title="Annual",
        publisher="Issuer",
        published_on="2024-04-30",
        accessed_on="2024-05-01",
        locator="p10",
        excerpt="Reviewed fixture",
        kind="primary",
        review="opened_and_checked",
    )


def quantity(value, metric="cash"):
    return dict(
        value=value,
        unit="shares" if metric == "shares" else "currency",
        source_ids=["s"],
        period_end="2023-12-31",
        period_start="2023-01-01" if metric in {"fcff", "ffo", "affo"} else None,
    )


def valuation(method):
    return dict(
        ticker="TEST",
        currency="USD",
        method=method,
        shares=quantity(10, "shares"),
        book_equity=quantity(1000),
        reit_cashflow=quantity(100, "affo"),
        assumption_rationale="Fixture assumptions, not measurements",
        ownership_basis="parent common shareholders",
        denominator_basis="common share count in fixture",
    )


def evidence(valuations):
    facts = []
    for metric, value in [("shares", 10), ("book_equity", 1000), ("affo", 100)]:
        q = quantity(value, metric)
        facts.append(
            dict(
                metric=metric,
                value=value,
                currency="USD",
                unit=q["unit"],
                period_type="annual",
                period_end=q["period_end"],
                period_start=q["period_start"],
                consolidation="consolidated",
                accounting_standard="US-GAAP",
                source_ids=["s"],
            )
        )
    return dict(
        schema_version=2,
        sources=[source()],
        financial_histories=[
            dict(
                ticker="TEST",
                profile="financial",
                currency="USD",
                expected_annual_ends=["2021-12-31", "2022-12-31", "2023-12-31"],
                latest_interim_end="2024-03-31",
                facts=facts,
            )
        ],
        valuations=valuations,
    )


def test_multiple_valuations_v2():
    data = evidence([valuation("residual_income"), valuation("reit_multiple")])
    ev = ResearchEvidence.model_validate(data)
    original = new_bundle("stock", {"market": "US"}, {"TEST": {"analysis": {}}})
    updated = resume(original, ev)
    assert len(updated["sections"]["TEST"]["filing_valuations"]) == 2
    assert all(
        v["status"] == "available"
        for v in updated["sections"]["TEST"]["filing_valuations"]
    )
    assert (
        updated["sections"]["TEST"]["filing_valuation"]["method"] == "residual_income"
    )
    data["valuations"].append(deepcopy(data["valuations"][0]))
    with pytest.raises(ValidationError):
        ResearchEvidence.model_validate(data)


def test_financial_ownership_and_unit_mismatch_are_rejected():
    data = evidence([valuation("residual_income")])
    data["valuations"][0]["ownership_basis"] = "consolidated"
    with pytest.raises(ValidationError, match="ownership"):
        ResearchEvidence.model_validate(data)
    data = evidence([valuation("residual_income")])
    data["financial_histories"][0]["facts"][0]["unit"] = "currency"
    with pytest.raises(ValidationError, match="unit mismatch"):
        ResearchEvidence.model_validate(data)


def ttm():
    return dict(
        metric="affo",
        definition="Fixture equity AFFO",
        value=30,
        currency="JPY",
        unit="currency",
        period_type="ttm",
        period_start="2023-01-01",
        period_end="2023-12-31",
        consolidation="consolidated",
        accounting_standard="JGAAP",
        source_ids=["s"],
        components=[
            dict(
                period_start="2023-01-01",
                period_end="2023-06-30",
                base_value=10,
                source_ids=["s"],
            ),
            dict(
                period_start="2023-07-01",
                period_end="2023-12-31",
                base_value=20,
                source_ids=["s"],
            ),
        ],
    )


def test_semiannual_ttm_reconciles():
    assert FinancialFact.model_validate(ttm()).base_value == 30
    half = ttm()
    half.update(period_type="fiscal_half", period_end="2023-06-30", components=[])
    assert FinancialFact.model_validate(half).period_type == "fiscal_half"


@pytest.mark.parametrize("change", ["overlap", "gap", "sum", "source"])
def test_ttm_refuses_false_aggregation(change):
    data = ttm()
    if change == "overlap":
        data["components"][1]["period_start"] = "2023-06-30"
    if change == "gap":
        data["components"][1]["period_start"] = "2023-07-02"
    if change == "sum":
        data["value"] = 40
    if change == "source":
        data["source_ids"] = ["other"]
    with pytest.raises(ValidationError):
        FinancialFact.model_validate(data)


def test_derived_quantity_rejects_mixed_period_or_wrong_sum():
    payload = dict(
        ticker="TEST",
        currency="USD",
        metric="corporate_adjustment",
        output=quantity(-100),
        terms=[
            dict(
                metric="corporate_cost",
                quantity=quantity(10),
                coefficient=-10,
                rationale="Assumed capitalization multiple",
            )
        ],
        rationale="Signed corporate value bridge",
    )
    assert DerivedQuantity.model_validate(payload).output.value == -100
    payload["terms"][0]["quantity"]["period_end"] = "2023-06-30"
    with pytest.raises(ValidationError):
        DerivedQuantity.model_validate(payload)


def test_segment_ledger_requires_complete_names_and_elimination():
    def flow(value):
        return {**quantity(value), "period_start": "2023-01-01"}

    payload = dict(
        ticker="TEST",
        currency="USD",
        period_start="2023-01-01",
        period_end="2023-12-31",
        axis="operating_segments",
        reported_segments=["A", "B"],
        source_ids=["s"],
        records=[
            dict(
                name=name,
                metric_name="revenue",
                quantity=flow(value),
                ownership_basis="consolidated",
                note="Original segment note",
            )
            for name, value in [("A", 100), ("B", 80)]
        ],
        consolidated_total=flow(150),
        elimination=flow(-30),
        reconciliation_note="Intersegment elimination",
    )
    assert SegmentLedger.model_validate(payload).consolidated_total.value == 150
    payload["elimination"]["value"] = 0
    with pytest.raises(ValidationError):
        SegmentLedger.model_validate(payload)
    payload["elimination"]["value"] = -30
    payload["records"].pop()
    with pytest.raises(ValidationError):
        SegmentLedger.model_validate(payload)


def saved():
    return new_bundle(
        "market",
        {"market": "US"},
        {
            "market": {
                "analysis": {
                    "market_type": "US",
                    "market_data": {"old": 1},
                    "credit_stress": {"label": "retained"},
                    "trend_ranking": {"items": []},
                }
            },
            "TEST": {"analysis": {"primary_conditions": {"conditions": []}}},
        },
    )


def test_refresh_summary_preserves_unrelated(monkeypatch):
    from src.services import market_dashboard_service as service
    from src.services.analysis_context import MarketContext

    original = saved()
    before = deepcopy(original)
    monkeypatch.setattr(
        service,
        "build_market_summary_context",
        lambda market: MarketContext(market_type=market, market_data={"new": 2}),
    )
    result = refresh(original, "summary", market_type="US")
    assert result["sections"]["market"]["analysis"]["credit_stress"] == {
        "label": "retained"
    }
    assert result["sections"]["market"]["analysis"]["market_data"] == {"new": 2}
    assert result["sections"]["TEST"] == original["sections"]["TEST"]
    assert original == before


def test_refresh_failure_retains_previous(monkeypatch):
    from src.services import market_dashboard_service as service

    def fail(*args):
        raise TimeoutError("private token not persisted")

    monkeypatch.setattr(service, "build_market_high_context", fail)
    original = saved()
    result = refresh(original, "credit-risk", market_type="US")
    assert (
        result["sections"]["market"]["analysis"]
        == original["sections"]["market"]["analysis"]
    )
    assert result["execution_status"] == "partial"
    assert "token" not in str(result)


@pytest.mark.parametrize("market,permission", [("JP", True), ("US", False)])
def test_refresh_options_scope(market, permission):
    with pytest.raises(ValueError):
        refresh(saved(), "options", market_type=market, allow_options=permission)


def test_interpretation_preserves_analysis():
    original = saved()
    data = dict(
        interpretations=[
            dict(
                scope="US",
                kind="market",
                run_id=original["run_id"],
                observations=["Saved credit observation"],
                counterevidence=["No forecast verification"],
                input_paths=["sections.market.analysis.credit_stress"],
            )
        ]
    )
    result = resume(original, ResearchEvidence.model_validate(data))
    assert result["sections"]["market"] == original["sections"]["market"]
    assert result["interpretations"][0]["run_id"] == original["run_id"]
    data["interpretations"][0]["input_paths"] = ["sections.market.analysis.missing"]
    with pytest.raises(ValueError):
        resume(original, ResearchEvidence.model_validate(data))


@pytest.mark.parametrize(
    "point",
    [
        "not-object",
        {"name": "2023-02-30", "price": 1},
        {"price": "1"},
        {"volume": True},
    ],
)
def test_snapshot_refuses_hostile_chart_point(point):
    data = new_bundle(
        "stock", {"market": "US"}, {"TEST": {"analysis": {"chart_data": [point]}}}
    )
    with pytest.raises(ValueError):
        validate_bundle(data)


def test_fixed_market_fields_preserve_shared_service_contract(monkeypatch):
    from src.research import runner
    from src.research.catalog import MARKET_FEATURES
    from src.services import market_dashboard_service as service
    from src.services.analysis_context import MarketContext, OptionContext

    context = MarketContext(market_type="US")
    for field in MARKET_FEATURES:
        if field not in {"options", "japan_conditions"}:
            setattr(
                context,
                field,
                {
                    "negative": -1.5,
                    "zero": 0,
                    "missing": None,
                    "condition": False,
                    "status": "research_only",
                },
            )
    context.options = OptionContext(status="unavailable")
    monkeypatch.setattr(
        service, "build_market_summary_context", lambda m: deepcopy(context)
    )
    for name in (
        "build_market_theme_flow_context",
        "build_market_high_context",
        "build_market_volatility_sentiment_context",
    ):
        monkeypatch.setattr(service, name, lambda m, base: base)
    result = runner.market("US", False)["analysis"]
    from src.research.bundle import plain

    assert result == plain(context)
    assert set(MARKET_FEATURES).issubset(result)


def test_fixed_all_stock_fields_preserve_shared_service_contract(monkeypatch):
    from pydantic import BaseModel, ConfigDict

    from src.research import runner
    from src.research.bundle import plain
    from src.research.catalog import STOCK_FEATURES
    from src.services import stock_dashboard_service as service

    class FixedContext(BaseModel):
        model_config = ConfigDict(extra="allow")
        info: dict
        stock_signal_context: dict

    values = {
        field: {
            "negative": -2,
            "zero": 0,
            "missing": None,
            "condition": False,
            "status": "insufficient_data",
        }
        for field in STOCK_FEATURES
    }
    values.update(info={"name": "TEST"}, news=[], chart_data=[])
    context = FixedContext.model_validate(values)
    monkeypatch.setattr(
        service, "build_stock_dashboard_context", lambda ticker: context
    )
    result = runner.stock("TEST", ResearchEvidence())["analysis"]
    assert result == plain(context)
    assert set(STOCK_FEATURES).issubset(result)
