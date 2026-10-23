"""Fixed-input acceptance for display bindings, replay and evidence reconciliation."""

import ast
import html
import json
import re
import shutil
import subprocess
from copy import deepcopy
from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

from src.research import comparison, runner
from src.research.bundle import new_bundle, validate_bundle
from src.research.catalog import MARKET_FEATURES, STOCK_FEATURES, feature_coverage
from src.research.evidence import ResearchEvidence
from src.research.filing_catalog import fetch_sec_catalog, select_filings
from src.research.financial_history import (
    FLOW_METRICS,
    PROFILE_METRICS,
    FinancialHistory,
)
from src.research.policy import synthesize
from src.research.render import ASSETS, render_dashboard


def history_series():
    return [
        {
            "label": "Index",
            "source_type": "direct_index",
            "points": [
                {"date": "2024-02-28", "price": 80},
                {"date": "2024-02-29", "price": 100},
                {"date": "2024-03-01", "price": 120},
                {"date": "2024-03-31", "price": 110},
            ],
        },
        {
            "label": "ETF代理",
            "source_type": "etf_proxy",
            "points": [
                {"date": "2024-02-29", "price": 1000},
                {"date": "2024-03-02", "price": 1200},
                {"date": "2024-03-31", "price": 900},
            ],
        },
    ]


def test_common_calendar_base_and_no_filling():
    result = comparison.compare(history_series(), "1mo")
    assert result["start"] == "2024-02-29"  # calendar month, leap-day clamp
    assert result["end"] == "2024-03-31"
    assert result["points"][0]["values"] == [100, 100]
    assert [row["date"] for row in result["points"]] == ["2024-02-29", "2024-03-31"]
    assert result["series"][0]["return_pct"] == pytest.approx(10)
    assert result["series"][1]["return_pct"] == pytest.approx(-10)
    assert result["series"][1]["latest"] == 900
    assert result["series"][1]["source_type"] == "etf_proxy"


def test_missing_short_and_empty_history_are_explicit():
    assert comparison.compare([], "6mo")["status"] == "unavailable"
    series = history_series()
    series[1]["points"] = series[1]["points"][:1]
    assert comparison.compare(series, "6mo")["status"] == "insufficient_data"
    assert comparison.compare(history_series(), "2y")["status"] == "partial"
    with pytest.raises(ValueError):
        comparison.compare([], "12mo")
    assert (
        comparison.comparison_views({"error_type": "Timeout"})["US"]["6mo"]["status"]
        == "unavailable"
    )


def test_topix_fallback_never_splices_or_relabels_index(monkeypatch):
    import requests

    def fail(*a, **k):
        raise requests.Timeout("redacted")

    monkeypatch.setattr(comparison.requests, "get", fail)
    calls = []
    monkeypatch.setattr(
        comparison,
        "_yahoo",
        lambda ticker, label, **kwargs: (
            calls.append((ticker, label, kwargs))
            or {"points": [], "warnings": [], "source_type": "etf_proxy"}
        ),
    )
    result = comparison._topix()
    assert calls == [("1306.T", "TOPIX連動ETF・代理", {"proxy": True})]
    assert result["source_type"] == "etf_proxy"
    assert result["warnings"]


def test_history_points_filter_future_nonfinite_duplicates():
    frame = pd.DataFrame(
        {"Close": [100, float("nan"), -1, 105]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2099-01-01"]),
    )
    assert comparison.history_points(frame) == [{"date": "2024-01-01", "price": 100}]
    assert comparison.history_points(pd.DataFrame()) == []


def test_snapshot_v1_readback_keeps_observation_unknown():
    bundle = new_bundle("stock", {"market": "US"}, {"TEST": {"analysis": {}}})
    bundle["schema_version"] = 1
    original = deepcopy(bundle)
    assert validate_bundle(bundle) == original
    html = render_dashboard(bundle)
    assert 'nav id="navigation"' in html and "connect-src 'none'" in html
    assert "個別株の保存結果" not in bundle  # render cannot mutate data
    assert bundle == original
    bundle["schema_version"] = 4
    with pytest.raises(ValueError):
        render_dashboard(bundle)


def test_all_reference_features_have_named_display_and_captured_inputs():
    market = {key: {"marker": f"market-{key}"} for key in MARKET_FEATURES}
    stock = {key: {"marker": f"stock-{key}"} for key in STOCK_FEATURES}
    bundle = new_bundle(
        "stock",
        {"market": "US"},
        {"market": {"analysis": market}, "TEST": {"analysis": stock}},
    )
    rendered = render_dashboard(bundle)
    for key, label in {**MARKET_FEATURES, **STOCK_FEATURES}.items():
        assert key in rendered and label in rendered
    rows = feature_coverage(bundle)
    assert len(rows) == len(MARKET_FEATURES) + len(STOCK_FEATURES)
    assert all(row["state"] == "captured" for row in rows)
    assert bundle["sections"]["TEST"]["analysis"] == stock


def test_connected_market_groups_cover_each_feature_once_without_acquisition():
    script = (ASSETS / "market.js").read_text(encoding="utf-8")
    groups = ast.literal_eval(
        script.split("const MARKET_GROUPS=", 1)[1].split(";", 1)[0]
    )
    keys = [key for _, _, fields in groups for key in fields]
    assert len(keys) == len(set(keys)) == len(MARKET_FEATURES)
    assert set(keys) == set(MARKET_FEATURES)
    assert "featureDetails(m,payload.market_features)" not in (
        ASSETS / "dashboard.js"
    ).read_text(encoding="utf-8")
    assert "fetch(" not in script and "XMLHttpRequest" not in script
    assert "openResearchPage('theme',r.theme)" in script


def test_inline_theme_expansion_and_fixed_mobile_navigation_contract():
    script = "\n".join(
        (ASSETS / name).read_text(encoding="utf-8")
        for name in ("specialized.js", "market.js")
    )
    style = (ASSETS / "dashboard.css").read_text(encoding="utf-8")
    assert (
        "representative_tickers" in script and "saved.find(s=>s.ticker===t)" in script
    )
    assert "aria-expanded" in script and "aria-controls" in script
    assert "body.append(detail)" in script  # details stay in the theme row group
    assert "themeExpanded" in script and "themeControls" in script
    assert "grid-template-rows:45px minmax(0,1fr)" in style
    assert "height:44px;min-height:44px;max-height:44px" in style


def display_js(parts, assertions):
    """Execute production display helpers with fixed inputs, without a browser."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable for JavaScript display-unit checks")
    snippets = []
    for filename, start, end in parts:
        source = (ASSETS / filename).read_text(encoding="utf-8")
        snippets.append(start + source.split(start, 1)[1].split(end, 1)[0])
    command = "const assert=require('node:assert/strict');\n"
    command += "\n".join(snippets) + "\n" + assertions
    completed = subprocess.run(
        [node, "-e", command], capture_output=True, text=True, timeout=15, check=False
    )
    assert completed.returncode == 0, completed.stderr


def test_display_comparison_single_series_and_common_date_boundaries():
    display_js(
        [("dashboard.js", "function subtractMonths(", "function comparison(market)")],
        """
const a={label:'Index',points:[{date:'2024-02-29',price:100},
 {date:'2024-03-01',price:120},{date:'2024-03-31',price:110}]};
const b={label:'ETF',source_type:'etf_proxy',points:[
 {date:'2024-02-29',price:1000},{date:'2024-03-02',price:1050},
 {date:'2024-03-31',price:900}]};
const result=alignComparison([a,b],'1mo');
assert.deepEqual(result.points.map(p=>p.date),['2024-02-29','2024-03-31']);
assert.deepEqual(result.points[0].values,[100,100]);
assert.ok(Math.abs(result.series[1].return_pct+10)<1e-9);
assert.equal(result.series[1].source_type,'etf_proxy');
const original=JSON.stringify(a),single=alignComparison([a,{label:'Missing',points:[]}],'1mo');
assert.equal(single.singleSeries,true);assert.deepEqual(single.missing,['Missing']);
assert.equal(single.points.length,3);assert.equal(JSON.stringify(a),original);
assert.equal(alignComparison([a,{label:'Other',points:[
 {date:'2024-03-03',price:1},{date:'2024-03-04',price:2}]}],'1mo').status,'insufficient_data');
assert.equal(alignComparison([{points:[{date:'2024-02-30',price:2},
 {date:'2024-03-01',price:0},{date:'2024-03-02',price:-1}]}],'1mo').status,'unavailable');
""",
    )


def test_display_normal_notes_are_not_errors_and_missing_is_not_success():
    display_js(
        [("dashboard.js", "function dataState(", "const DATA_LABELS=")],
        """
assert.equal(dataState({status:'available',error:'通常の処理説明'}),'available');
assert.equal(dataState({status:'ok',note:'倍率の推測補正なし'}),'available');
assert.equal(dataState({status:'available',is_stale:true}),'stale');
assert.equal(dataState({status:'research_only'}),'research_only');
assert.equal(dataState({status:'unavailable',error:'取得失敗'}),'unavailable');
assert.equal(dataState({status:'stale',error:'再取得失敗'}),'stale');
assert.equal(dataState({is_partial:true,error:'部分取得'}),'partial');
assert.equal(dataState({error:'旧形式の取得失敗'}),'unavailable');
""",
    )


def test_display_signed_geometry_keeps_zero_missing_and_outside_range():
    display_js(
        [("charts.js", "function signedBar(", "function valuationRange(")],
        """
function el(tag,cls,text){return {tag,cls,text,children:[],style:{},
 append(...items){this.children.push(...items)},setAttribute(){},
 classList:{add(){}}};}
function numericNode(value,cls,text){return el('span',cls,text)}
const pct=v=>Number.isFinite(v)?v+'%':'未確認',number=v=>String(v);
const negative=signedBar(-5,10);assert.equal(negative.children[0].children[1].style.left,'25%');
assert.equal(negative.children[0].children[1].style.width,'25%');
assert.equal(signedBar(0,10).children[1].text,'0%');
assert.equal(signedBar(null,10).children[0].children.length,1);
assert.equal(signedBar(null,10).children[1].text,'未確認');
const range=pricePosition(120,80,100);assert.equal(range.children[0].children[1].style.left,'100%');
assert.equal(range.children[0].children[0].style.width,'50%');
assert.equal(range.children[1].children[2].text,'高値 100');
""",
    )


def test_display_connection_caption_uses_actual_scope_and_values():
    display_js(
        [("market.js", "function savedObservation(", "function connectionPanel(")],
        """
const number=(v,d)=>v.toFixed(d),pct=v=>v+'%';
const c={observations:[{id:'a',label:'米10年',value:48,unit:'bp',quality:'available'},
 {id:'b',label:'米実質10年',value:49,unit:'bp',quality:'available'}]};
const relation={id:'名目と実質金利',from:'a',to:'b',kind:'supports'};
const text=relationCaption(relation,c);assert.ok(text.includes('48.0 bp'));
assert.ok(text.includes('49.0 bp'));assert.ok(!text.includes('強気'));
c.observations[1].quality='stale';assert.ok(relationCaption(relation,c).includes('前回値'));
assert.equal(displayObservation({quality:'unavailable',value:12}).value,null);
assert.equal(displayObservation({quality:'available',value:0}).value,0);
""",
    )


def test_primary_groups_keep_unselected_stage_and_entry_failures_visible():
    display_js(
        [
            (
                "specialized.js",
                "function primaryConditionPanel(",
                "function unsavedStockPage(",
            )
        ],
        """
function el(tag,cls,text){return {tag,cls,text,children:[],
 append(...items){this.children.push(...items)}};}
const panel=title=>el('section','',title),dateText=v=>v;
const input={conditions:[
 {label:'200日線が上向き',status:'pass',value:'1%'},
 {label:'株価 > 50日線',status:'pass',value:'100'},
 {label:'52週安値から30%以上',status:'fail',value:'10%'},
 {label:'日足Entryトリガー',status:'pass',value:'成立'},
 {label:'50MAからのATR拡張',status:'fail',value:'5ATR'},
 {label:'200MAトレンド',status:'unknown',value:'履歴不足'}]};
const original=JSON.stringify(input),groups=primaryConditionPanel(input).children[0].children;
assert.equal(groups.length,6);
assert.ok(JSON.stringify(groups[0]).includes('52週安値から30%以上'));
assert.ok(JSON.stringify(groups[5]).includes('5ATR'));
assert.ok(JSON.stringify(groups[5]).includes('履歴不足'));
assert.equal(JSON.stringify(input),original);
""",
    )


@pytest.mark.parametrize("version", [1, 2])
def test_embedded_render_is_optional_and_preserves_saved_inputs(version):
    bundle = new_bundle("stock", {"market": "US"}, {"TEST": {"analysis": {}}})
    bundle["schema_version"] = version
    original = deepcopy(bundle)
    for embedded in (False, True):
        rendered = render_dashboard(bundle, embedded=embedded)
        encoded = re.search(r'<pre id="payload" hidden>(.*?)</pre>', rendered, re.S)
        assert encoded
        payload = json.loads(html.unescape(encoded.group(1)))
        assert payload["embedded"] is embedded
        assert payload["bundle"] == original
        assert "connect-src 'none'" in rendered
    assert bundle == original


def source():
    return {
        "id": "s",
        "ticker": "TEST",
        "url": "https://issuer.example/ir/annual",
        "title": "Annual",
        "publisher": "Issuer",
        "published_on": "2025-01-01",
        "accessed_on": date.today().isoformat(),
        "locator": "Financial statements p.10",
        "excerpt": "Reviewed table",
        "kind": "primary",
        "review": "opened_and_checked",
    }


def ledger(profile="general", currency="USD"):
    ends = ["2021-12-31", "2022-12-31", "2023-12-31"]
    periods = [("annual", end) for end in ends] + [("interim", "2024-03-31")]
    facts = []
    for kind, end in periods:
        for metric in PROFILE_METRICS[profile]:
            facts.append(
                {
                    "metric": metric,
                    "value": 0 if metric == "cash" else 10,
                    "currency": currency,
                    "unit": "million_shares"
                    if metric == "shares"
                    else "percent"
                    if metric == "roe"
                    else "million",
                    "period_type": kind,
                    "period_end": end,
                    "period_start": end[:4] + "-01-01"
                    if metric in FLOW_METRICS
                    else None,
                    "consolidation": "consolidated",
                    "accounting_standard": "US-GAAP" if currency == "USD" else "IFRS",
                    "source_ids": ["s"],
                }
            )
    return {
        "ticker": "TEST",
        "profile": profile,
        "currency": currency,
        "expected_annual_ends": ends,
        "latest_interim_end": "2024-03-31",
        "facts": facts,
    }


@pytest.mark.parametrize("profile", ["general", "financial", "reit"])
@pytest.mark.parametrize("currency", ["USD", "JPY"])
def test_jp_us_financial_history_completeness_and_conversion(profile, currency):
    item = ledger(profile, currency)
    evidence = ResearchEvidence.model_validate(
        {"sources": [source()], "financial_histories": [item]}
    )
    result = evidence.for_ticker("TEST")["financial_history"]
    assert result["status"] == "available"
    assert result["facts"][0]["base_value"] == 10000000
    item["facts"].pop()
    assert FinancialHistory.model_validate(item).completeness()["status"] == "partial"


@pytest.mark.parametrize(
    "mutation", ["currency", "unit", "period", "unreviewed", "duplicate", "standalone"]
)
def test_financial_evidence_rejects_mixing_and_false_completeness(mutation):
    item = ledger()
    original_source = source()
    if mutation == "currency":
        item["facts"][0]["currency"] = "JPY"
    elif mutation == "unit":
        item["facts"][0]["unit"] = "shares"
    elif mutation == "period":
        item["facts"][0]["period_start"] = "2021-09-01"
    elif mutation == "unreviewed":
        original_source["review"] = "unverified"
    elif mutation == "duplicate":
        item["facts"].append(deepcopy(item["facts"][0]))
    else:
        item["facts"][0]["consolidation"] = "standalone"
        result = ResearchEvidence.model_validate(
            {"sources": [original_source], "financial_histories": [item]}
        )
        assert result.for_ticker("TEST")["financial_history"]["status"] == "partial"
        return
    with pytest.raises(ValidationError):
        ResearchEvidence.model_validate(
            {"sources": [original_source], "financial_histories": [item]}
        )


def quantity(value, *, shares=False, flow=False):
    return {
        "value": value,
        "unit": "shares" if shares else "currency",
        "source_ids": ["s"],
        "period_end": "2023-12-31",
        "period_start": "2023-01-01" if flow else None,
    }


@pytest.mark.parametrize("method", ["fcff_dcf", "residual_income", "reit_multiple"])
def test_three_primary_valuation_methods_have_cases_and_no_model(method):
    val = {
        "ticker": "TEST",
        "currency": "USD",
        "method": method,
        "cash": quantity(0),
        "debt": quantity(0),
        "shares": quantity(10, shares=True),
        "assumption_rationale": "Explicit fixture scenarios",
        "fcff": quantity(100, flow=True),
        "book_equity": quantity(1000),
        "reit_cashflow": quantity(100, flow=True),
    }
    result = (
        ResearchEvidence.model_validate({"sources": [source()], "valuations": [val]})
        .valuations[0]
        .calculate()
    )
    assert result["status"] == "available"
    assert len(result["cases"]) == 3
    if method == "reit_multiple":
        assert result["cases"][1]["value"] == 140
    if method == "residual_income":
        assert result["cases"][1]["value"] == pytest.approx(114.285714)
    val["cash"]["period_end"] = "2023-09-30"
    with pytest.raises(ValidationError):
        ResearchEvidence.model_validate({"sources": [source()], "valuations": [val]})


def test_ledger_valuation_cannot_use_mismatched_amount():
    item = ledger()
    val = {
        "ticker": "TEST",
        "currency": "USD",
        "method": "fcff_dcf",
        "cash": quantity(0),
        "debt": quantity(10),
        "shares": quantity(10, shares=True),
        "assumption_rationale": "Fixture",
    }
    with pytest.raises(ValidationError):
        ResearchEvidence.model_validate(
            {"sources": [source()], "financial_histories": [item], "valuations": [val]}
        )


def test_resume_keeps_all_saved_calculations_and_never_calls_provider(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("A resume must not fetch")

    monkeypatch.setattr(runner, "market", forbidden)
    monkeypatch.setattr(runner, "stock", forbidden)
    monkeypatch.setattr(runner, "theme", forbidden)
    bundle = new_bundle(
        "policy",
        {"market": "US"},
        {
            "TEST": {
                "analysis": {
                    "primary_conditions": {
                        "conditions": [
                            {"label": "VCP", "status": "fail", "value": "未検出"}
                        ]
                    },
                    "chart_data": [{"price": 100}],
                }
            }
        },
    )
    original = deepcopy(bundle)
    result = runner.resume(
        bundle, ResearchEvidence.model_validate({"sources": [source()]})
    )
    assert (
        result["sections"]["TEST"]["analysis"]
        == original["sections"]["TEST"]["analysis"]
    )
    assert result["sections"]["TEST"]["filings"]["sources"][0]["id"] == "s"
    assert (
        result["sections"]["policy"]["stocks"][0]["counterevidence"][0]["label"]
        == "VCP"
    )
    assert result["resumed_from"]["network_requested"] is False
    assert result["run_id"] != original["run_id"] and bundle == original


def test_policy_reads_exact_theme_order_no_invented_stock_scores():
    sections = {
        "theme": {
            "ranking": {
                "items": [
                    {"theme": "First", "performance_1m": -10},
                    {"theme": "Second", "performance_1m": 100},
                ]
            }
        },
        "market": {
            "analysis": {
                "strategy_regime": {"label": "待ち", "invalidation": "支持割れ"}
            }
        },
    }
    result = synthesize(sections, "US")
    assert result["observations"][-1]["observation"] == "First / Second"
    assert result["stance"] == "待ち" and result["invalidation"] == "支持割れ"
    assert not result["stocks"] and result["status"] == "research_only"
    assert "synthesis" not in result


def test_sec_catalog_deduplicates_amendments_and_preserves_unreviewed():
    columns = {
        "form": ["10-Q", "10-K", "10-K/A", "10-K", "10-K"],
        "reportDate": [
            "2024-03-31",
            "2023-12-31",
            "2023-12-31",
            "2022-12-31",
            "2021-12-31",
        ],
        "filingDate": [
            "2024-05-01",
            "2024-02-01",
            "2024-06-01",
            "2023-02-01",
            "2022-02-01",
        ],
        "accessionNumber": ["0000320193-24-000001"] * 5,
        "primaryDocument": ["report.htm"] * 5,
    }
    result = select_filings(columns, "320193")
    assert len(result["annual"]) == 3
    assert result["annual"][0]["form"] == "10-K/A"
    assert result["latest_interim"]["period_end"] == "2024-03-31"
    assert result["annual"][0]["review"] == "unverified"
    assert fetch_sec_catalog("AAPL", "320193", "")["status"] == "unavailable"
    with pytest.raises(ValueError):
        fetch_sec_catalog("AAPL", "../bad", "fixture@example.invalid")


def test_japan_quote_never_disables_us_key_with_unsupported_request(monkeypatch):
    from src import finnhub_client

    monkeypatch.setattr(
        finnhub_client,
        "_get_client",
        lambda: pytest.fail("Unsupported Yahoo .T symbol must not reach Finnhub"),
    )
    assert finnhub_client.get_quote("1306.T") is None


def test_payload_script_injection_is_escaped_in_all_views():
    bundle = new_bundle(
        "stock",
        {"market": "US"},
        {
            "TEST": {
                "analysis": {
                    "info": {"name": "</pre><script>location='https://bad'</script>"}
                }
            }
        },
    )
    rendered = render_dashboard(bundle)
    assert "</pre><script>location=" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "innerHTML" not in rendered
    json.dumps(bundle, allow_nan=False)


@pytest.mark.parametrize(
    "section", [{"market": []}, {"TEST": {"analysis": []}}, {"themes": {"JP": []}}]
)
def test_malformed_snapshot_rejected_before_render(section):
    bundle = new_bundle("market", {"market": "US"}, {})
    bundle["sections"] = section
    with pytest.raises(ValueError):
        render_dashboard(bundle)


def test_nested_market_failures_are_not_completed():
    bundle = new_bundle(
        "overview",
        {"market": "US"},
        {
            "markets": {"US": {"error_type": "TimeoutError"}, "JP": {"analysis": {}}},
            "themes": {"US": {}, "JP": {}},
        },
    )
    assert bundle["execution_status"] == "partial"


def test_model_guard_blocks_cached_client_and_configuration(monkeypatch):
    from src import gemini_client

    monkeypatch.setenv("INVESTMENT_RESEARCH_NO_MODEL", "1")
    monkeypatch.setattr(gemini_client, "_client", object())
    assert gemini_client.get_gemini_client() is None
    assert gemini_client.configure_gemini("not-a-real-key") is False


def test_fomo_is_opt_in_us_only(monkeypatch):
    from src.services import market_dashboard_service as service

    monkeypatch.setattr(service, "build_market_summary_context", lambda *a: {})
    for name in (
        "build_market_theme_flow_context",
        "build_market_high_context",
        "build_market_volatility_sentiment_context",
    ):
        monkeypatch.setattr(service, name, lambda market, context: context)
    calls = []
    monkeypatch.setattr(
        service,
        "build_fomo_scan_context",
        lambda: calls.append(1) or {"status": "available"},
    )
    assert "fomo_scan" not in runner.market("US", False)["analysis"]
    assert (
        runner.market("US", False, True)["analysis"]["fomo_scan"]["status"]
        == "available"
    )
    assert calls == [1]
    with pytest.raises(ValueError):
        runner.run("market", market_type="JP", scan_fomo=True)
    with pytest.raises(ValueError):
        runner.run("overview", allow_options=True)


def test_finite_inputs_cannot_produce_infinite_valuation():
    from src.services.equity_valuation_service import calculate_dcf, calculate_sotp

    assert (
        calculate_dcf(
            starting_fcf=1e308,
            growth_rate=1,
            wacc=0.09,
            terminal_growth=0.02,
            net_debt=0,
            shares=1,
        )
        is None
    )
    result = calculate_sotp(
        [{"metric": 1e308, "multiple": 1}, {"metric": 1e308, "multiple": 1}],
        net_debt=0,
        shares=1,
    )
    assert result["per_share"] is None and result["status"] == "partial"
    json.dumps(result, allow_nan=False)


def test_feature_coverage_retains_zero_and_explicit_unavailable():
    from src.research.catalog import coverage_state

    assert coverage_state(0) == "captured"
    assert coverage_state(False) == "captured"
    assert (
        coverage_state({"status": "unavailable", "reason": "missing"}) == "unavailable"
    )
    assert coverage_state({"status": "research_only"}) == "research_only"


def test_v1_policy_replay_does_not_require_v2_synthesis(tmp_path):
    from src.research.render import save_bundle

    bundle = new_bundle("policy", {"market": "US"}, {"policy": {"synthesis": "legacy"}})
    bundle["schema_version"] = 1
    output = save_bundle(bundle, tmp_path / "replay")
    assert (output / "dashboard.html").exists()
    assert json.loads((output / "research.json").read_text(encoding="utf-8")) == bundle


def test_attached_snapshots_are_preserved_and_validated_before_writing(tmp_path):
    from src.research.render import save_bundle

    main = new_bundle("overview", {"market": "US"}, {})
    stock = new_bundle("stock", {"market": "JP"}, {"TEST.T": {"analysis": {}}})
    original = deepcopy([main, stock])
    output = save_bundle(main, tmp_path / "combined", [stock])
    assert (
        json.loads((output / "attached_01.json").read_text(encoding="utf-8")) == stock
    )
    assert [main, stock] == original
    with pytest.raises(ValueError):
        save_bundle(main, tmp_path / "invalid", [{"schema_version": 99}])
    assert not (tmp_path / "invalid").exists()
