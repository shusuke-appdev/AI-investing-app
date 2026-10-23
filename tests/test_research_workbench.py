"""Daily orchestration and loopback UI boundaries, without real providers."""

import json
import re
import sys
import threading
from copy import deepcopy
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from src.research import workbench as module
from src.research.bundle import new_bundle
from src.research.local_server import create_server
from src.research.render import save_bundle
from src.storage.atomic_json import write_json


@pytest.mark.parametrize(
    "args,scope", [([], "all"), (["--scope", "JP"], "JP"), (["--market", "US"], "US")]
)
def test_cli_broad_request_uses_single_shared_update(
    monkeypatch, tmp_path, args, scope
):
    from scripts import research

    calls = []

    class FakeWorkbench:
        def __init__(self, root):
            pass

        def update(self, chosen, *, profile="standard"):
            assert profile == "standard"
            calls.append(chosen)
            return tmp_path

    monkeypatch.setattr(module, "Workbench", FakeWorkbench)
    monkeypatch.setattr(sys, "argv", ["research.py", "update", *args])
    assert research.main() == 0
    assert calls == [scope]


def seed():
    result = new_bundle(
        "update",
        {"market": "US"},
        {
            "markets": {
                "US": {"analysis": {"marker": "old-US"}},
                "JP": {"analysis": {"marker": "old-JP"}},
            },
            "themes": {"US": {"ranking": {}}, "JP": {"ranking": {}}},
            "comparisons": {},
            "AAPL": {
                "analysis": {
                    "chart_data": [{"name": "2026-09-01", "price": 100}],
                    "marker": "reviewed",
                },
                "filings": {"sources": []},
            },
        },
    )
    result["saved_stock_origins"] = {
        "AAPL": {"run_id": result["run_id"], "created_at": result["created_at"]}
    }
    result["saved_interpretations"] = [
        {
            "run_id": "source-run",
            "interpretations": [
                {"scope": "AAPL", "observations": ["Saved, not regenerated"]}
            ],
            "inputs": {"evidence": {"sources": []}},
        }
    ]
    return result


def providers(monkeypatch, calls):
    def market(key, options):
        calls.append(("market", key, options))
        return {"analysis": {"marker": "new-" + key, "strategy_regime": {"label": key}}}

    def theme(key):
        calls.append(("theme", key))
        return {
            "ranking": {"items": [{"theme": key}]},
            "leaders": {"data": {"candidates": [{"ticker": "TEST"}]}},
        }

    def comparisons(markets):
        calls.append(("comparisons", markets))
        return {
            key: {"series": [{"points": [{"date": "2026-09-01", "price": 10}]}] * 2}
            for key in markets
        }

    monkeypatch.setattr(module.runner, "market", market)
    monkeypatch.setattr(module.runner, "theme", theme)
    monkeypatch.setattr(module, "fetch_comparisons", comparisons)
    monkeypatch.setattr(
        module.runner, "diagnostics", lambda: {"network_requested": False}
    )
    monkeypatch.setattr(
        module.runner,
        "stock",
        lambda *args: pytest.fail("No individual deep dive in broad update"),
    )


@pytest.mark.parametrize(
    "scope,markets", [("all", ("US", "JP")), ("US", ("US",)), ("JP", ("JP",))]
)
def test_broad_update_and_scope_preserve_individual_evidence(
    monkeypatch, scope, markets
):
    calls = []
    providers(monkeypatch, calls)
    previous = seed()
    unchanged = deepcopy(previous)
    result = module.update_research(previous, scope, profile="advanced")
    assert previous == unchanged
    assert result["sections"]["AAPL"] == previous["sections"]["AAPL"]
    assert result["saved_stock_origins"] == previous["saved_stock_origins"]
    assert result["saved_interpretations"] == previous["saved_interpretations"]
    assert result["execution_status"] == "completed"
    assert result["inputs"]["allow_options"] is False
    assert result["inputs"]["scan_fomo"] is False
    assert ("comparisons", markets) in calls
    for market in markets:
        assert ("market", market, False) in calls
        assert (
            result["sections"]["policies"][market]["observations"][3]["observation"]
            == market
        )
        assert result["sections"]["policies"][market]["stocks"] == []
        assert result["sections"]["themes"][market]["leaders"]["data"]["candidates"]
    for market in set(("US", "JP")) - set(markets):
        assert (
            result["sections"]["markets"][market]
            == previous["sections"]["markets"][market]
        )


def test_partial_failures_keep_old_values_not_fresh(monkeypatch):
    providers(monkeypatch, [])
    monkeypatch.setattr(
        module.runner,
        "market",
        lambda *_: {"analysis": {"marker": "attempt", "errors": ["missing"]}},
    )
    monkeypatch.setattr(
        module.runner, "theme", lambda *_: {"error_type": "TimeoutError"}
    )
    result = module.update_research(seed(), "JP", profile="advanced")
    assert result["execution_status"] == "partial"
    packet = result["sections"]["markets"]["JP"]
    assert packet["analysis"]["marker"] == "old-JP"
    assert packet["attempted_analysis"]["analysis"]["marker"] == "attempt"
    assert packet["refresh_failure"]["previous_result_retained"] is True
    assert result["sections"]["themes"]["JP"]["refresh_failure"]


@pytest.mark.parametrize(
    "status",
    [
        {"status": "partial"},
        {"is_partial": True},
        {"is_stale": True},
        {"error": "timeout"},
    ],
)
def test_provider_partial_status_is_not_a_complete_update(monkeypatch, status):
    providers(monkeypatch, [])
    monkeypatch.setattr(
        module.runner,
        "market",
        lambda *_: {
            "analysis": {
                "marker": "fresh basic",
                "data_status": [{"name": "flow", **status}],
            }
        },
    )
    result = module.update_research(seed(), "US", profile="advanced")
    assert result["execution_status"] == "partial"
    assert result["sections"]["markets"]["US"]["analysis"]["marker"] == "fresh basic"


def test_load_saved_pointer_and_new_stock_without_network(tmp_path, monkeypatch):
    previous = seed()
    previous["created_at"] = "2026-09-01T00:00:00+00:00"
    previous["saved_stock_origins"]["AAPL"]["created_at"] = previous["created_at"]
    runs = tmp_path / ".states" / "research_runs"
    save_bundle(previous, runs / "first")
    write_json(
        tmp_path / ".states" / "research_workbench" / "current.json",
        {"directory": "first"},
    )
    latest = new_bundle(
        "stock", {"market": "US"}, {"AAPL": {"analysis": {"marker": "new-stock"}}}
    )
    save_bundle(latest, runs / "second")
    (runs / "second" / "attached_01.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        module.runner, "market", lambda *_: pytest.fail("Opening is offline")
    )
    wb = module.Workbench(tmp_path)
    assert wb.bundle["sections"]["markets"] == previous["sections"]["markets"]
    assert wb.bundle["sections"]["AAPL"]["analysis"]["marker"] == "new-stock"
    assert wb.snapshot_status()["result"] == "saved"


def test_workspace_save_roundtrip_and_failed_save_preserves_screen(
    tmp_path, monkeypatch
):
    providers(monkeypatch, [])
    wb = module.Workbench(tmp_path)
    output = wb.update(profile="advanced")
    assert output
    restored = module.Workbench(tmp_path)
    assert restored.bundle == wb.bundle
    old = wb.dashboard()
    pointer = (
        tmp_path / ".states" / "research_workbench" / "current.json"
    ).read_bytes()
    monkeypatch.setattr(
        module, "save_bundle", lambda *_: (_ for _ in ()).throw(OSError("SECRET"))
    )
    assert wb.update(profile="advanced") is None
    assert wb.dashboard() == old
    assert (
        tmp_path / ".states" / "research_workbench" / "current.json"
    ).read_bytes() == pointer
    assert "SECRET" not in wb.snapshot_status()["message"]


def test_os_lock_and_background_double_update(tmp_path, monkeypatch):
    path = tmp_path / "test.lock"
    with module.update_lock(path), pytest.raises(OSError), module.update_lock(path):
        pass
    with module.update_lock(path):
        pass
    wb = module.Workbench(tmp_path)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def updating(previous, scope, progress, *, profile="standard"):
        entered.set()
        assert release.wait(10)
        return previous

    original = wb.update

    def wrapped(scope, profile="standard"):
        try:
            return original(scope, profile)
        finally:
            finished.set()

    monkeypatch.setattr(module, "update_research", updating)
    monkeypatch.setattr(wb, "update", wrapped)
    assert wb.begin("all")
    assert entered.wait(10)
    assert wb.begin("JP") is False
    release.set()
    assert finished.wait(10)


def test_local_server_csrf_host_body_and_no_repo_file_access(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module.Workbench,
        "begin",
        lambda self, scope, profile="standard": calls.append(scope) or True,
    )
    server = create_server(tmp_path, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def request(path, body=None, headers=None):
        req = Request(base + path, data=body, headers=headers or {})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, response.read().decode()
        except HTTPError as exc:
            return exc.code, exc.read().decode()

    try:
        code, page = request("/")
        assert code == 200 and "投資更新" in page
        token = re.search(r"const token='([^']+)'", page)[1]
        body = json.dumps({"scope": "all"}).encode()
        headers = {
            "Content-Type": "application/json",
            "Origin": base,
            "X-Research-Token": token,
        }
        assert request("/api/status")[0] == 200
        assert request("/dashboard")[0] == 200
        assert request("/.env")[0] == 404
        assert request("/../../README.md")[0] == 404
        assert request("/", headers={"Host": "attacker.example"})[0] == 403
        assert (
            request(
                "/api/update", body, {**headers, "Origin": "https://attacker.example"}
            )[0]
            == 403
        )
        assert (
            request("/api/update", body, {**headers, "X-Research-Token": "bad"})[0]
            == 403
        )
        assert request("/api/update", b"[]", headers)[0] == 400
        assert request("/api/update", b"x" * 1025, headers)[0] == 400
        assert request("/api/update", body, headers)[0] == 202
        assert calls == ["all"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
