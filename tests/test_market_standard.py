"""Fixed evidence and call-graph regressions for the standard market workflow."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src.advisor.signal_modeling import purge_training_indices
from src.persistent_cache import PersistentJsonCache
from src.provider_result import FetchResult
from src.research import runner, standard
from src.research.bundle import new_bundle, validate_bundle
from src.research.connections import connect, relationship
from src.research.public_sources import (
    event_row,
    parse_events,
    parse_mof,
    reviewed_flow,
)
from src.research.workbench import update_research
from src.services.price_integrity import usable_history


@pytest.fixture(autouse=True)
def fixed_observation_clock(monkeypatch):
    import src.research.public_sources as sources

    class FixedTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 9, 12, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(standard, "datetime", FixedTime)
    monkeypatch.setattr(sources, "datetime", FixedTime)


def history(scale=1):
    frame = pd.DataFrame(
        {
            "Close": np.linspace(100, 200, 270) * scale,
            "High": np.linspace(101, 201, 270) * scale,
            "Low": np.linspace(99, 199, 270) * scale,
            "Volume": 1000.0,
        },
        index=pd.bdate_range(end="2026-10-08", periods=270),
    )
    frame.attrs["fetch_metadata"] = {
        "source": "https://finance.yahoo.com/",
        "fetched_at": "2026-10-08T10:00:00+00:00",
        "cache_status": "live",
        "is_stale": False,
        "price_basis": "adjusted OHLCV",
    }
    frame.attrs["price_integrity"] = {
        "reason": "倍率を推測した自動補正は行っていません。"
    }
    return frame


def mocks(monkeypatch):
    import src.economic_data_provider as economic

    calls = []

    def prices(tickers):
        calls.extend(tickers)
        return {t: history() for t in tickers}

    monkeypatch.setattr(standard, "fetch_prices", prices)
    monkeypatch.setattr(
        economic,
        "fetch_fred_series",
        lambda *a, **kw: FetchResult(
            data=pd.DataFrame(
                {s: np.linspace(3, 4, 30) for s in a[0]},
                index=pd.bdate_range(end="2026-10-08", periods=30),
            ),
            source="fred",
            fetched_at="2026-10-08",
            cache_status="live",
        ),
    )
    monkeypatch.setattr(
        standard,
        "official_inputs",
        lambda: {
            "mof": {
                "points": [{"date": "2026-10-08", "value": 1.2}],
                "source": "https://www.mof.go.jp/",
                "fetched_at": "2026-10-08",
                "cache_status": "live",
            },
            "events": [],
            "event_sources": [],
            "jpx": {"status": "unavailable", "reason": "Permission not confirmed"},
        },
    )
    for name in ("market", "theme", "stock"):
        monkeypatch.setattr(
            runner, name, lambda *a: pytest.fail("Excluded legacy workflow invoked")
        )
    return calls


def test_standard_deduplicates_and_does_not_call_legacy(monkeypatch):
    calls = mocks(monkeypatch)
    result = runner.run("overview")
    assert result["inputs"]["profile"] == "standard"
    assert len(calls) == len(set(calls))
    for market in ("US", "JP"):
        analysis = result["sections"]["markets"][market]["analysis"]
        assert "short_horizon_forecast" not in analysis
        assert analysis["connected"]["version"] == "connected-market-v1"
        assert (
            analysis["connected"] == result["sections"]["policies"][market]["connected"]
        )
    with pytest.raises(ValueError):
        runner.run("market", allow_options=True)


def test_successful_observation_notes_do_not_become_acquisition_errors(monkeypatch):
    mocks(monkeypatch)
    result = runner.run("overview")
    for market in ("US", "JP"):
        rows = result["sections"]["markets"][market]["analysis"]["data_status"]
        available = [r for r in rows if r["status"] == "available"]
        assert available
        assert all(r["error"] is None for r in available)
        assert any(r["note"] for r in available)
        for row in rows:
            if row["status"] != "available":
                assert row["note"] is None


def test_standard_update_preserves_old_models_dates_stocks_and_original(monkeypatch):
    mocks(monkeypatch)
    old = new_bundle(
        "update",
        {"market": "US"},
        {
            "markets": {
                "US": {
                    "analysis": {
                        "short_horizon_forecast": {"as_of": "2024-01-02", "value": 123}
                    }
                }
            },
            "AAPL": {"filings": {"sources": []}},
        },
    )
    original = deepcopy(old)
    result = update_research(old)
    assert old == original
    analysis = result["sections"]["markets"]["US"]["analysis"]
    assert (
        analysis["short_horizon_forecast"]
        == original["sections"]["markets"]["US"]["analysis"]["short_horizon_forecast"]
    )
    assert (
        analysis["field_updates"]["short_horizon_forecast"]["status"] == "not_updated"
    )
    assert (
        analysis["field_updates"]["short_horizon_forecast"]["observed_on"]
        == "2024-01-02"
    )
    assert result["sections"]["AAPL"] == old["sections"]["AAPL"]
    validate_bundle(json.loads(json.dumps(result)))
    repeated = update_research(result)
    assert (
        repeated["sections"]["markets"]["US"]["analysis"]["field_updates"][
            "short_horizon_forecast"
        ]
        == analysis["field_updates"]["short_horizon_forecast"]
    )


def test_theme_coverage_each_period_and_registered_order():
    basket = {
        "theme": {
            "measurement_tickers": ["A", "B", "C", "D", "E"],
            "all_tickers": ["B", "A", "E", "D", "C"],
            "method": "test",
        }
    }
    frames = {t: history() for t in ("SPY", "A", "B", "C")}
    row = standard.rank_themes("US", frames, basket)["items"][0]
    assert row["coverage_6m"] == 60
    assert row["rank"] == 1
    assert row["relative_6m"] == 0
    assert row["representative_tickers"][:3] == ["B", "A", "E"]
    frames["C"] = history().tail(10)
    row = standard.rank_themes("US", frames, basket)["items"][0]
    assert row["rank_1w"] == 1 and row["rank_1m"] is None and row["rank_6m"] is None
    frames["C"].attrs["fetch_metadata"]["is_stale"] = True
    assert standard.rank_themes("US", frames, basket)["items"][0]["rank_1w"] is None


def test_missing_session_is_not_compressed_or_forward_filled():
    frame = history().drop(history().index[-5])
    assert standard.returns(frame, history(), 21) == (None, None, [])


def test_split_and_invalid_prices_stop_derived_analysis():
    frame = history()
    frame.loc[frame.index[-1], "Close"] = 5000
    guarded = usable_history(frame)
    assert (
        guarded.empty
        and guarded.attrs["price_integrity"]["status"] == "suspect_price_basis"
    )
    assert (
        usable_history(guarded).attrs["price_integrity"]["status"]
        == "suspect_price_basis"
    )
    assert frame["Close"].iloc[-1] == 5000  # No guessed repair.
    for bad in (0, -1, float("nan"), float("inf")):
        frame.loc[frame.index[-1], "Close"] = bad
        assert usable_history(frame).empty
    frame.attrs["price_integrity"] = {"status": "ok"}
    frame["Close"] = "100"
    assert usable_history(frame).empty


def obs(
    value,
    *,
    parent="A",
    window="21sessions",
    market="US",
    day="2026-10-08",
    quality="available",
):
    return {
        "value": value,
        "parents": [parent],
        "window": window,
        "market": market,
        "observed_on": day,
        "period_start": "2026-09-08",
        "period_end": day,
        "source": "test",
        "quality": quality,
    }


@pytest.mark.parametrize(
    "other,expected",
    [
        (obs(-1, parent="B"), "weakens"),
        (obs(1, parent="B"), "supports"),
        (obs(0, parent="B"), "reference"),
        (obs(1), "reference"),
        (obs(None, parent="B"), "incomparable"),
        (obs(1, parent="B", market="JP"), "reference"),
        (obs(1, parent="B", day="2026-10-07"), "incomparable"),
        (obs(1, parent="B", quality="stale"), "incomparable"),
    ],
)
def test_relations_require_actual_comparability(other, expected):
    assert relationship(obs(1), other) == expected


def test_connection_cases_do_not_collapse_into_single_stance():
    observations = [
        {"id": "index:return_6m", **obs(1)},
        {"id": "participation:rsp", **obs(-1, parent="B", window="126sessions")},
        {"id": "index:ma200_gap", **obs(1, window="200sessions")},
        {"id": "index:ma20_gap", **obs(-1, window="20sessions")},
    ]
    observations[0]["window"] = "126sessions"
    result = connect(observations, [])
    assert len(result["relations"]) == 7
    assert result["relations"][0]["kind"] == "weakens"
    assert result["relations"][1]["kind"] == "different_horizon"
    assert "score" not in result and "stance" not in result


def test_label_end_is_strictly_before_test_start_after_missing_rows():
    positions = np.array([0, 1, 4, 5, 7, 8, 9, 10, 11])
    kept = purge_training_indices(np.arange(7), np.array([7, 8]), positions, horizon=5)
    assert positions[kept].max() + 5 < positions[7]
    assert 3 not in kept  # 5+5 == test start is excluded.


def test_concurrent_cache_is_atomic_and_leaves_no_fixed_temp(tmp_path):
    cache = PersistentJsonCache(tmp_path, "test")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda n: cache.write(
                    "same", {"writer": n, "values": list(range(100))}
                ),
                range(50),
            )
        )
    result = cache.read("same", fresh_seconds=60)
    assert result.status == "fresh" and result.payload["values"] == list(range(100))
    assert list(tmp_path.glob("*.tmp")) == []


def test_import_order_does_not_create_cycle():
    for first, second in [
        ("market_dashboard_workflows", "market_dashboard_service"),
        ("market_dashboard_service", "market_dashboard_workflows"),
    ]:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import src.services.{first}; import src.services.{second}",
            ],
            capture_output=True,
            timeout=25,
        )
        assert result.returncode == 0, result.stderr


def test_mof_percent_negative_and_no_magnitude_guess():
    rows = parse_mof(
        "国債金利情報,,,,(単位 : %)\n基準日,2年,10年\nR8.10.1,1.0,-0.1\nR8.10.2,1.1,1.234\n"
    )
    assert rows[-1] == {"date": "2026-10-02", "value": 1.234}
    assert rows[0]["value"] == -0.1
    with pytest.raises(ValueError):
        parse_mof("unknown,10年\n2026-10-01,1234")


def test_events_dst_unknown_time_and_no_prediction():
    summer = event_row(
        "CPI", date(2026, 7, 1), "test", local_time="08:30", zone="America/New_York"
    )
    winter = event_row(
        "CPI", date(2026, 12, 1), "test", local_time="08:30", zone="America/New_York"
    )
    assert "T12:30" in summer["utc_time"] and "T13:30" in winter["utc_time"]
    assert event_row("会合", date(2026, 10, 1), "test")["utc_time"] is None
    html = "<table><caption>表 2026年</caption><tbody><tr><td>10月29日（木）・30日（金）</td></tr></tbody></table>"
    assert parse_events(html, "BOJ", 2026)[0]["date"] == "2026-10-30"


def test_jpx_permission_amount_scope_nonoverlap_and_four_week_sum():
    rows = [
        {
            "period_start": f"2026-09-{day:02}",
            "period_end": f"2026-09-{day + 4:02}",
            "net_amount": amount,
            "source": "https://www.jpx.co.jp/test.xlsx",
            "scope": "cash_equity_foreigners",
            "unit": "JPY",
            "permission_confirmed": True,
            "opened_and_checked": True,
            "permission_basis": "synthetic test only",
            "locator": "sheet value foreign balance",
            "checked_on": "2026-10-09",
        }
        for day, amount in [(1, -10), (8, 0), (15, 10), (22, 20)]
    ]
    assert reviewed_flow(rows)["four_week_net"] == 20
    for field, value in [
        ("permission_confirmed", False),
        ("unit", "shares"),
        ("scope", "futures"),
        ("net_amount", float("inf")),
    ]:
        bad = deepcopy(rows)
        bad[0][field] = value
        with pytest.raises(ValueError):
            reviewed_flow(bad)
    with pytest.raises(ValueError):
        reviewed_flow(rows + [deepcopy(rows[0])])


def test_old_observations_are_not_fresh_theme_confirmations():
    old = history()
    old.index = pd.bdate_range(end="2026-09-01", periods=len(old))
    ranking = standard.rank_themes(
        "US",
        {"SPY": old, "A": old},
        {"T": {"all_tickers": ["A"], "measurement_tickers": ["A"]}},
    )
    assert ranking["items"][0]["rank"] is None
    assert ranking["items"][0]["coverage_6m"] == 0


def test_reviewed_input_roundtrip_and_check_dates_stay_original(monkeypatch):
    from src.research.public_sources import validate_market_inputs

    mocks(monkeypatch)
    input_data = {"version": "reviewed-market-input-v1", "jpx_weeks": []}
    previous = new_bundle("update", {"market": "US"}, {})
    result = update_research(previous, "JP", market_inputs=input_data)
    assert result["inputs"]["market_inputs"] == input_data
    assert (
        result["sections"]["markets"]["JP"]["analysis"]["connected"]["jpx"]["status"]
        == "unavailable"
    )
    repeated = update_research(result, "JP")
    assert repeated["inputs"]["market_inputs"] == input_data
    with pytest.raises(ValueError):
        validate_market_inputs({"version": "bad", "jpx_weeks": []})


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "3"])
def test_flow_alignment_rejects_non_numeric_confirmation(value):
    from src.services.market_dashboard_workflows import build_flow_alignment_context

    dates = {
        "period_start": "2026-09-01",
        "period_end": "2026-10-01",
        "window": "20sessions",
    }
    flow = {
        **dates,
        "market": "US",
        "leaders": [{"ticker": "X", "relative_return_20d": value}],
    }
    sectors = {
        **dates,
        "primary_market": "US",
        "markets": {"US": {"leaders": [{"ticker": "X", "relative_return_20d": 1}]}},
    }
    assert build_flow_alignment_context(flow, sectors)["alignment_label"] != "整合"


def test_rate_percent_levels_and_bp_changes_do_not_guess_scale(monkeypatch):
    import src.market_index_provider as indices
    import src.rate_provider as rates

    data = pd.DataFrame(
        {"DGS10": [-0.1, 0, 4.25]}, index=pd.bdate_range(end="2026-10-08", periods=3)
    )
    monkeypatch.setattr(
        rates,
        "fetch_fred_series",
        lambda *a, **kw: FetchResult(
            data=data,
            source="FRED",
            fetched_at="2026-10-08",
            is_stale=True,
            cache_status="stale_cache",
        ),
    )
    frame = rates.rate_history("^TNX", "5d")
    assert frame.Close.tolist() == [-0.1, 0, 4.25]
    assert frame.attrs["fetch_metadata"]["is_stale"]
    monkeypatch.setattr(rates, "rate_history", lambda *a: frame)
    _, _, row = indices._fetch_yfinance_market_item("10Y", "^TNX")
    assert row["price"] == 4.25 and row["change"] == 425
    assert row["unit"] == "%" and row["change_unit"] == "bp"


def test_all_seven_connection_cases_keep_scope_and_counterevidence():
    definitions = [
        ("index:return_6m", 10, "126sessions", "index"),
        ("participation:rsp", -2, "126sessions", "rsp"),
        ("index:ma200_gap", 5, "200sessions", "index"),
        ("index:ma20_gap", -1, "20sessions", "index"),
        ("index:return_1m", 3, "21sessions", "index"),
        ("credit:change_1m", 20, "21sessions", "credit"),
        ("vix:change_1m", -2, "21sessions", "vix"),
        ("DGS10:change_1m", 10, "21sessions", "nominal"),
        ("DFII10:change_1m", -10, "21sessions", "real"),
        ("JPY=X:return_1m", 2, "21sessions", "fx"),
        ("CL=F:return_1m", 3, "21sessions", "oil"),
    ]
    rows = [
        {
            "id": identifier,
            "label": identifier,
            "unit": "%",
            **obs(value, window=window, parent=parent),
        }
        for identifier, value, window, parent in definitions
    ]
    result = connect(rows, [{"theme": "T"}])
    assert [r["kind"] for r in result["relations"]] == [
        "weakens",
        "different_horizon",
        "weakens",
        "reference",
        "weakens",
        "supports",
        "reference",
    ]
    assert all(
        all(
            r[k]
            for k in (
                "observation",
                "conditional",
                "alternative",
                "invalidation",
                "next_check",
            )
        )
        for r in result["relations"]
    )
    assert result["scenarios"] == result["relations"]
    rows[4]["market"] = "JP"
    assert connect(rows, [])["relations"][2]["kind"] == "reference"
    rows[0]["market"] = "JP"
    rows = [r for r in rows if r["id"] != "participation:rsp"]
    rows.append(
        {
            "id": "participation:sample",
            "label": "限定母集団",
            "unit": "%",
            **obs(50, window="200sessions", parent="sample"),
        }
    )
    assert "IWM" not in connect(rows, [])["relations"][0]["next_check"]


def test_memory_history_keeps_original_source_date_and_stale_failure():
    from src.cache import ttl_cache
    from src.provider_result import memory_result

    frame = history()
    frame.attrs["fetch_metadata"].update(cache_status="stale_cache", is_stale=True)
    original = FetchResult(
        data=frame,
        fetched_at="2026-10-01",
        source="original-source",
        is_stale=True,
        cache_status="stale_cache",
        error="latest fetch failed",
    )
    calls = []

    @ttl_cache(namespace="test.standard.memory-state", on_hit=memory_result)
    def fetch():
        calls.append(1)
        return original

    fetch.clear_cache()
    assert fetch() is original
    cached = fetch()
    assert calls == [1]
    assert cached.fetched_at == "2026-10-01" and cached.is_stale
    assert (
        cached.error == "latest fetch failed" and cached.cache_status == "stale_cache"
    )
    assert cached.data.attrs["fetch_metadata"]["cache_layer"] == "memory"
    assert "cache_layer" not in original.data.attrs["fetch_metadata"]
    fetch.clear_cache()


def test_news_memory_hit_does_not_claim_new_acquisition(monkeypatch):
    import src.news_provider as news

    calls = []
    monkeypatch.setattr(news, "is_configured", lambda: True)
    monkeypatch.setattr(news, "get_auth_status", lambda: "valid")
    monkeypatch.setattr(
        news, "_finnhub_get_company_news", lambda *a: calls.append(1) or []
    )
    monkeypatch.setattr(news, "utc_now_iso", lambda: "2026-10-08T09:00:00+00:00")
    news.get_stock_news_result.clear_cache()
    news.get_stock_news_with_status.clear_cache()
    first = news.get_stock_news_with_status("CACHE-TEST")
    second = news.get_stock_news_with_status("CACHE-TEST")
    assert first["provider_status"]["cache_status"] == "live"
    assert second["provider_status"]["cache_status"] == "memory_cache"
    assert (
        second["provider_status"]["fetched_at"]
        == first["provider_status"]["fetched_at"]
    )
    assert calls == [1] and first["source_status"] == "empty"
    news.get_stock_news_result.clear_cache()
    news.get_stock_news_with_status.clear_cache()


def test_index_memory_metadata_keeps_old_date_and_unknown_sources():
    from src.market_index_provider import _memory_indices

    old = {
        "A": {"price": 10, "fetched_at": "2026-10-01", "cache_status": "live"},
        "B": {"price": 20},
        "C": {"price": 30, "cache_status": "stale_cache", "is_stale": True},
    }
    cached = _memory_indices(old, 5)
    assert cached["A"]["cache_status"] == "memory_cache"
    assert cached["A"]["fetched_at"] == "2026-10-01"
    assert cached["C"]["cache_status"] == "stale_cache" and cached["C"]["is_stale"]
    assert "cache_status" not in cached["B"] and "fetched_at" not in cached["B"]
    assert old["A"]["cache_status"] == "live"
