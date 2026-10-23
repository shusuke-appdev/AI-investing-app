import json
from dataclasses import dataclass
from datetime import date

import pytest
from pydantic import ValidationError

from src.research import runner
from src.research.bundle import new_bundle, plain
from src.research.evidence import ResearchEvidence
from src.research.render import render_dashboard, save_bundle
from src.services import company_research_service as valuation


def evidence_payload():
    return {
        "sources": [
            {
                "id": "annual",
                "ticker": "TEST",
                "url": "https://issuer.example/investors/annual",
                "title": "Annual",
                "publisher": "Test",
                "published_on": "2025-01-01",
                "accessed_on": date.today().isoformat(),
                "locator": "p. 12",
                "excerpt": "Revenue increased",
                "kind": "primary",
                "review": "opened_and_checked",
            }
        ],
        "claims": [
            {
                "ticker": "TEST",
                "category": "financial",
                "text": "Revenue",
                "source_ids": ["annual"],
                "period": "FY2024",
                "currency": "USD",
                "unit": "million",
                "value": 10,
            }
        ],
    }


def test_evidence_retains_units_and_does_not_certify_truth():
    result = ResearchEvidence.model_validate(evidence_payload()).for_ticker("TEST")
    assert result["status"] == "partial"
    assert result["claims"][0]["value"] == 10
    assert result["claims"][0]["unit"] == "million"
    assert "do not verify" in result["verification"]
    assert ResearchEvidence().for_ticker("TEST")["status"] == "unavailable"


@pytest.mark.parametrize(
    "change",
    ["ticker", "unreviewed", "future", "duplicate", "nan", "unit", "url", "unknown"],
)
def test_bad_evidence_rejected(change):
    payload = evidence_payload()
    if change == "ticker":
        payload["claims"][0]["ticker"] = "OTHER"
    elif change == "unreviewed":
        payload["sources"][0]["review"] = "unverified"
    elif change == "future":
        payload["sources"][0]["published_on"] = "2999-01-01"
    elif change == "duplicate":
        payload["sources"].append(payload["sources"][0].copy())
    elif change == "nan":
        payload["claims"][0]["value"] = float("nan")
    elif change == "unit":
        payload["claims"][0]["unit"] = ""
    elif change == "url":
        payload["sources"][0]["url"] = "https://key:secret@example.com"
    else:
        payload["claims"][0]["source_ids"] = ["missing"]
    with pytest.raises(ValidationError):
        ResearchEvidence.model_validate(payload)


def test_bundle_roundtrip_and_safe_render(tmp_path):
    bundle = new_bundle(
        "stock",
        {"market": "US"},
        {"TEST": {"name": "</pre><script>alert(1)</script>", "missing": None}},
    )
    output = save_bundle(bundle, tmp_path / "run")
    assert json.loads((output / "research.json").read_text(encoding="utf-8")) == bundle
    rendered = render_dashboard(bundle)
    assert "</pre><script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "connect-src 'none'" in rendered
    with pytest.raises(FileExistsError):
        save_bundle(bundle, output)


def test_plain_preserves_missing_and_dates():
    @dataclass
    class Sample:
        value: float

    assert plain({"value": Sample(float("nan")), "date": date(2025, 1, 1)}) == {
        "value": {"value": None},
        "date": "2025-01-01",
    }
    with pytest.raises(TypeError):
        plain(object())


def test_policy_bounded_and_failure_isolated(monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "market", lambda *a: {"status": "available"})
    monkeypatch.setattr(
        runner,
        "theme",
        lambda *a: {
            "leaders": {"data": {"candidates": [{"ticker": str(n)} for n in range(10)]}}
        },
    )

    def stock(ticker, evidence):
        calls.append(ticker)
        if ticker == "1":
            raise RuntimeError("secret-provider-url")
        return {"status": "available"}

    monkeypatch.setattr(runner, "stock", stock)
    bundle = runner.run("policy", profile="advanced")
    assert calls == ["0", "1", "2", "3", "4"]
    assert bundle["sections"]["1"]["status"] == "unavailable"
    assert "secret-provider-url" not in json.dumps(bundle)
    assert bundle["inputs"]["allow_options"] is False


def test_market_options_are_opt_in(monkeypatch):
    from src.services import market_dashboard_service as service

    calls = []
    monkeypatch.setattr(service, "build_market_summary_context", lambda *a: {})
    for name in [
        "build_market_theme_flow_context",
        "build_market_high_context",
        "build_market_volatility_sentiment_context",
    ]:
        monkeypatch.setattr(service, name, lambda market, context: context)
    monkeypatch.setattr(
        service,
        "build_market_options_context",
        lambda market, context: calls.append(market) or context,
    )
    runner.market("US", False)
    runner.market("JP", True)
    assert not calls
    runner.market("US", True)
    assert calls == ["US"]


def test_registered_discovery_never_calls_model(monkeypatch):
    from src.services import theme_leader_service as service

    def fail(*args, **kwargs):
        raise AssertionError("Model discovery must not run")

    monkeypatch.setattr(service, "discover_external_theme_tickers", fail)
    monkeypatch.setattr(
        service, "build_trend_ranking_context", lambda *a, **k: {"items": []}
    )
    result = service.build_registered_theme_leaders("US")
    assert result.status == "unavailable"


def test_missing_cash_debt_and_nonfinite_inputs():
    info = {"freeCashflow": 150, "current_price": 100, "share_outstanding": 10}
    assert valuation.build_equity_valuation(info)["status"] == "unavailable"
    assert (
        valuation.build_equity_valuation({**info, "totalCash": 0, "totalDebt": 0})[
            "status"
        ]
        == "available"
    )
    assert (
        valuation.calculate_dcf(
            starting_fcf=100,
            growth_rate=0.05,
            wacc=0.1,
            terminal_growth=0.02,
            net_debt=float("nan"),
            shares=10,
        )
        is None
    )
    result = valuation.calculate_sotp(
        [{"metric": 100, "multiple": 8}], net_debt=100, shares=10
    )
    assert result["per_share"] == 70


def test_runner_validation():
    with pytest.raises(ValueError):
        runner.run("stock")
    with pytest.raises(ValueError):
        runner.run("unknown")
    with pytest.raises(ValueError):
        runner.run("market", market_type="XX")


def test_failed_workflow_remains_saved_as_failed(monkeypatch):
    def fail(*args):
        raise RuntimeError("provider error")

    monkeypatch.setattr(runner, "stock", fail)
    result = runner.run("stock", ticker="TEST")
    assert result["execution_status"] == "failed"
    assert result["inputs"]["evidence"]["schema_version"] == 1


def test_stock_wrapper_preserves_existing_context(monkeypatch):
    from src.services import stock_dashboard_service, stock_trade_analysis_service

    @dataclass
    class Context:
        info: dict
        stock_signal_context: dict
        primary_conditions: dict

    context = Context({"name": "TEST"}, {"ticker": "TEST"}, {"stage2": "unavailable"})
    monkeypatch.setattr(
        stock_dashboard_service, "build_stock_dashboard_context", lambda ticker: context
    )
    monkeypatch.setattr(
        stock_trade_analysis_service,
        "build_stock_trade_analysis",
        lambda values: {"inputs": values},
    )
    result = runner.stock("TEST", ResearchEvidence())
    assert result["analysis"] == plain(context)
    assert result["valuation"]["status"] == "unavailable"
    assert result["filing_valuation"]["status"] == "unavailable"
    assert result["entry_reference"]["inputs"] == context.stock_signal_context


def test_external_evidence_uses_existing_security_checks():
    payload = evidence_payload()
    second = {
        **payload["sources"][0],
        "id": "independent",
        "kind": "independent",
        "url": "https://news.example/story",
    }
    payload["sources"].append(second)
    payload["external_candidates"] = [
        {
            "ticker": "TEST",
            "exchange": "NASDAQ",
            "company_name": "Test",
            "theme": "Cloud",
            "business_relationship": "Cloud revenue",
            "evidence_date": date.today().isoformat(),
            "official_domain": "issuer.example",
            "source_ids": ["annual", "independent"],
        }
    ]
    evidence = ResearchEvidence.model_validate(payload)
    discovery = evidence.discovery("US", ["Cloud"])
    assert [item["ticker"] for item in discovery["validated"]] == ["TEST"]
    assert discovery["model"] == "Codex evidence"
    assert not evidence.discovery("US", ["Other"])["validated"]
    payload["sources"][1]["kind"] = "primary"
    with pytest.raises(ValidationError):
        ResearchEvidence.model_validate(payload)


def valuation_payload(method="fcff_dcf"):
    quantity = {
        "value": 100,
        "unit": "currency",
        "source_ids": ["annual"],
        "period_end": "2024-12-31",
    }
    return {
        "ticker": "TEST",
        "currency": "USD",
        "method": method,
        "cash": {**quantity, "value": 20},
        "debt": {**quantity, "value": 50},
        "shares": {**quantity, "unit": "shares", "value": 10},
        "fcff": {**quantity, "period_start": "2024-01-01"},
        "assumption_rationale": "Scenario inputs, not observed values",
    }


def test_source_linked_valuation_rejects_mixed_periods():
    payload = evidence_payload()
    payload["valuations"] = [valuation_payload()]
    result = ResearchEvidence.model_validate(payload).valuations[0].calculate()
    assert result["status"] == "available"
    assert len(result["cases"]) == 3
    payload["valuations"][0]["fcff"]["period_end"] = "2024-09-30"
    with pytest.raises(ValidationError):
        ResearchEvidence.model_validate(payload)


def test_sotp_requires_complete_segments_adjustments_and_sources():
    payload = evidence_payload()
    entry = valuation_payload("sotp")
    entry["segments"] = [
        {
            "name": "Cloud",
            "metric": entry.pop("fcff"),
            "metric_name": "EBIT",
            "multiple": 8,
            "multiple_rationale": "Comparable enterprise/EBIT assumption",
        }
    ]
    entry["all_reported_segments"] = ["Cloud", "Other"]
    entry["corporate_adjustment"] = {**entry["cash"], "value": -10}
    payload["valuations"] = [entry]
    assert (
        ResearchEvidence.model_validate(payload).valuations[0].calculate()["per_share"]
        is None
    )
    entry["all_reported_segments"] = ["Cloud"]
    assert (
        ResearchEvidence.model_validate(payload).valuations[0].calculate()["per_share"]
        == 76
    )
    entry["debt"]["source_ids"] = ["unknown"]
    with pytest.raises(ValidationError):
        ResearchEvidence.model_validate(payload)
