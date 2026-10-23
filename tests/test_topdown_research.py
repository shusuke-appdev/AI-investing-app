"""Behavioral regressions for market participation and quarterly evidence."""

from copy import deepcopy
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from src.research.bundle import new_bundle, validate_bundle
from src.research.evidence import ResearchEvidence
from src.research.quarterly import Quarter, evaluate_quarters
from src.research.topdown import (
    breadth,
    distribution_days,
    rotation,
    trend,
    volume_signals,
)


def history(count=400):
    dates = pd.bdate_range(end=date.today(), periods=count)
    close = np.linspace(100, 200, count)
    frame = pd.DataFrame(
        {
            "Close": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Volume": np.full(count, 1000.0),
        },
        index=dates,
    )
    frame.attrs["fetch_metadata"] = {
        "source": "https://finance.yahoo.com/",
        "is_stale": False,
        "fetched_at": dates[-1].isoformat(),
        "price_basis": "adjusted OHLCV",
    }
    return frame


def quarters():
    ends = pd.date_range("2023-03-31", periods=7, freq="QE")
    rows = []
    for i, end in enumerate(ends):
        revenue = 100 if i < 4 else [110, 120, 140][i - 4]
        eps = 1 if i < 4 else [1.1, 1.3, 1.8][i - 4]
        margin = 0.1 if i < 4 else [0.11, 0.13, 0.16][i - 4]
        rows.append(
            Quarter(
                ticker="TEST",
                period_start=(end - pd.offsets.QuarterEnd() + timedelta(days=1)).date(),
                period_end=end.date(),
                revenue=revenue,
                diluted_eps=eps,
                parent_net_income=revenue * margin,
                currency="USD",
                accounting_basis="US_GAAP",
                ownership_basis="parent_common",
                consolidation="consolidated",
                split_basis="same_source_split_adjusted",
                source="https://example.com/ir",
            ).model_dump(mode="json")
        )
    return rows


def test_medium_up_short_down_remain_separate():
    frame = history()
    frame.iloc[-1, frame.columns.get_loc("Close")] = 188
    result = trend(frame)
    assert result["label"] == "上昇基調"
    assert result["short_term"] == "20日線下"


def test_breadth_missing_history_and_calendar_are_not_zero_filled():
    bm = history()
    short = history(100)
    gap = history().drop(bm.index[-30])
    result = breadth(["A", "B", "C"], {"A": bm, "B": short, "C": gap}, bm)
    latest = result["latest"]
    assert latest["above_20"] == 100
    assert latest["above_50"] is None
    assert latest["counts"]["above_200"]["denominator"] == 1
    assert latest["above_200"] is None  # insufficient 60%/three-member coverage
    assert len(result["history"]) == 60


def test_distribution_window_recovery_and_missing_volume():
    frame = history(55)
    frame["Close"] = 100.0
    frame.loc[frame.index[30] :, "Close"] = 99.0
    frame.loc[frame.index[30], "Volume"] = 2000
    assert distribution_days(frame)["count"] == 1
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                {"Close": [99], "High": [100], "Low": [98], "Volume": [1000]},
                index=[frame.index[-1] + pd.offsets.BDay()],
            ),
        ]
    )
    assert distribution_days(frame)["count"] == 0
    assert distribution_days(frame)["expired"][-1]["reason"] == "25営業日窓の外"
    frame.loc[frame.index[-2], "Close"] = 104
    assert any(
        r["reason"] == "発生日終値から5%回復"
        for r in distribution_days(frame)["expired"]
    )
    frame.loc[frame.index[-1], "Volume"] = 0
    assert distribution_days(frame)["count"] is None


def test_pocket_pivot_includes_first_down_day_and_no_down_days_is_unknown():
    frame = history(60)
    assert volume_signals(frame)["pocket_pivot"] is None
    frame.loc[frame.index[-11], "Close"] = frame.Close.iloc[-12] - 1
    frame.loc[frame.index[-11], "Volume"] = 3000
    frame.loc[frame.index[-1], "Volume"] = 2000
    assert volume_signals(frame)["pocket_pivot"] is False
    frame.loc[frame.index[-1], "Volume"] = 4000
    assert volume_signals(frame)["pocket_pivot"] is True


def test_rotation_is_relative_not_positive_absolute_return():
    bm = history()
    stock = history()
    stock["Close"] = np.linspace(100, 150, len(stock))
    result = rotation(["A"], {"A": stock}, bm)
    assert result["strength"] < 0
    assert len(result["trail"]) == 12
    assert "相対劣後" in result["quadrant"]


def test_code33_acceleration_turnaround_and_missing_are_distinct():
    rows = quarters()
    result = evaluate_quarters(rows)
    assert result["code33"] is True
    assert result["verification"] == "自動取得・未照合"
    rows[-1]["revenue"] = rows[-2]["revenue"]
    assert evaluate_quarters(rows)["code33"] is False
    rows = quarters()
    rows[0]["diluted_eps"] = -1
    result = evaluate_quarters(rows)
    assert result["code33"] is None
    assert result["comparisons"][0]["turnaround"] is True
    assert evaluate_quarters(quarters()[-4:])["status"] == "insufficient_data"
    assert evaluate_quarters(quarters(), "financial")["status"] == "not_applicable"


@pytest.mark.parametrize(
    "key,value",
    [
        ("currency", "JPY"),
        ("split_basis", "different"),
        ("ownership_basis", "unconfirmed"),
    ],
)
def test_code33_rejects_mixed_definitions(key, value):
    rows = quarters()
    rows[-1][key] = value
    assert evaluate_quarters(rows)["status"] == "incomparable"


def test_quarter_rejects_cumulative_bool_and_fabricated_review():
    record = quarters()[-1]
    for changed in [
        {"period_start": "2024-01-01"},
        {"diluted_eps": True},
        {"review": "opened_and_checked"},
    ]:
        with pytest.raises(ValidationError):
            Quarter.model_validate(record | changed)
    with pytest.raises(ValueError):
        ResearchEvidence(
            schema_version=3, quarterly_records=[Quarter.model_validate(record)]
        )


def test_bundle_v3_reconciles_financial_flags_and_keeps_v1_v2_readable():
    result = evaluate_quarters(quarters())
    bundle = new_bundle(
        "screen",
        {"market": "US"},
        {"markets": {"US": {"analysis": {"quarterly_fundamentals": {"TEST": result}}}}},
    )
    assert validate_bundle(bundle)["schema_version"] == 3
    corrupt = deepcopy(bundle)
    corrupt["sections"]["markets"]["US"]["analysis"]["quarterly_fundamentals"]["TEST"][
        "code33"
    ] = False
    with pytest.raises(ValueError):
        validate_bundle(corrupt)
    for version in (1, 2):
        assert validate_bundle(
            new_bundle("market", {"market": "US"}, {}) | {"schema_version": version}
        )


def test_financial_checkpoint_resume_keeps_old_review(monkeypatch, tmp_path):
    from src.research import fundamentals

    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    calls = []
    result = evaluate_quarters(quarters()) | {
        "ticker": "TEST",
        "fetched_at": fundamentals.utc_now_iso(),
        "attempts": [],
    }
    monkeypatch.setattr(
        fundamentals, "acquire", lambda *a: calls.append(a[0]) or deepcopy(result)
    )
    bundle = new_bundle(
        "screen",
        {"market": "US"},
        {
            "markets": {
                "US": {
                    "analysis": {
                        "topdown": {
                            "screening": [{"ticker": "TEST", "profile": "general"}]
                        }
                    }
                }
            }
        },
    )
    first = fundamentals.refresh_fundamentals(bundle, ("US",), root=tmp_path)
    second = fundamentals.refresh_fundamentals(bundle, ("US",), root=tmp_path)
    assert calls == ["TEST"]
    assert first["counts"]["success"] == 1
    assert second["counts"]["cached"] == 1
    bundle["sections"]["markets"]["US"]["analysis"]["quarterly_fundamentals"]["TEST"][
        "reviewed_previous"
    ] = {"verification": "一次資料確認済み", "marker": "original"}
    fundamentals.refresh_fundamentals(bundle, ("US",), root=tmp_path)
    assert (
        bundle["sections"]["markets"]["US"]["analysis"]["quarterly_fundamentals"][
            "TEST"
        ]["reviewed_previous"]["marker"]
        == "original"
    )


def test_sec_parser_excludes_cumulative_eps_and_keeps_accession_basis():
    from src.research.fundamentals import sec_quarters

    record = {
        "start": "2024-01-01",
        "end": "2024-03-31",
        "accn": "0000000001-24-000001",
        "filed": "2024-04-20",
        "form": "10-Q",
        "val": 100,
    }

    def fact(unit):
        return {"units": {unit: [record, record | {"end": "2024-09-30", "val": 300}]}}

    result = sec_quarters(
        "TEST",
        {
            "cik": 1,
            "facts": {
                "us-gaap": {
                    "Revenues": fact("USD"),
                    "NetIncomeLoss": fact("USD"),
                    "EarningsPerShareDiluted": fact("USD/shares"),
                }
            },
        },
        "2024-04-20",
    )
    assert len(result) == 1
    assert result[0]["period_end"] == "2024-03-31"
    assert "0000000001-24-000001" in result[0]["split_basis"]


def test_provider_fallback_reports_failure_without_exception_secret(monkeypatch):
    from src.research import fundamentals

    def fail(*args):
        raise ValueError("sensitive request URL must not leak")

    monkeypatch.setattr(fundamentals, "sec_json", fail)
    monkeypatch.setattr(fundamentals, "yahoo_quarters", fail)
    result = fundamentals.acquire("TEST", "general", "1")
    assert result["status"] == "unavailable"
    assert "sensitive" not in str(result)


def test_missing_relative_benchmark_keeps_absolute_theme_and_sample():
    from src.research.standard import rank_themes
    from src.research.topdown import build_topdown

    frames = {"^N225": history(), "A": history(), "B": history(), "C": history()}
    baskets = {"sample": {"all_tickers": ["A", "B", "C"]}}
    result = rank_themes("JP", frames, baskets)
    assert result["items"][0]["rank"] is None
    assert result["items"][0]["performance_6m"] > 0
    # Actual registered JP universe is absent in this fixture, so no fabricated breadth.
    data = build_topdown("JP", frames, result)
    assert data["benchmark_status"] == "unavailable"
    assert data["breadth"]["latest"]["above_200"] is None


def test_saved_screening_export_and_financial_modes_do_not_refresh_stocks(
    monkeypatch, tmp_path
):
    from src.research import workbench

    original = new_bundle(
        "update",
        {"market": "US"},
        {
            "markets": {
                "US": {"analysis": {"topdown": {"screening": [{"ticker": "TEST"}]}}}
            },
            "TEST": {"analysis": {"original_date": "2024-01-01"}},
        },
    )
    monkeypatch.setattr(workbench, "saved_workspace", lambda _: deepcopy(original))
    monkeypatch.setattr(workbench, "render_dashboard", lambda *a, **kw: "saved")
    monkeypatch.setattr(
        workbench,
        "update_research",
        lambda *a, **kw: pytest.fail("Price update not requested"),
    )
    from src.research import fundamentals

    monkeypatch.setattr(
        fundamentals, "refresh_fundamentals", lambda *a, **kw: {"status": "partial"}
    )
    captured = []

    def save(value, directory):
        captured.append(deepcopy(value))
        directory.mkdir(parents=True)
        return directory

    monkeypatch.setattr(workbench, "save_bundle", save)
    app = workbench.Workbench(tmp_path)
    assert app.update("US", mode="fundamentals")
    assert captured[0]["sections"]["TEST"] == original["sections"]["TEST"]
    assert captured[0]["execution_status"] == "partial"


def test_quarter_resume_preserves_analysis_and_rejects_tampered_saved_condition():
    from src.research.runner import resume

    rows = quarters()
    for row in rows:
        row.update(
            review="opened_and_checked",
            source_ids=["reviewed"],
            published_on="2024-11-01",
        )
    source = dict(
        id="reviewed",
        ticker="TEST",
        url="https://example.com/ir",
        title="Test reviewed financial statement",
        publisher="Test issuer",
        published_on="2024-11-01",
        accessed_on="2024-11-02",
        locator="Standalone quarter comparison table",
        excerpt="Fixture",
        kind="primary",
        review="opened_and_checked",
    )
    original = new_bundle(
        "stock",
        {"market": "US"},
        {
            "TEST": {
                "analysis": {"original_date": "2024-01-01"},
                "filing_valuation": {"status": "original"},
                "filings": {"accounting_reviews": []},
            }
        },
    )
    updated = resume(
        original,
        ResearchEvidence(schema_version=3, quarterly_records=rows, sources=[source]),
    )
    packet = updated["sections"]["TEST"]
    assert packet["analysis"] == original["sections"]["TEST"]["analysis"]
    assert (
        packet["filing_valuation"] == original["sections"]["TEST"]["filing_valuation"]
    )
    assert packet["quarterly_fundamentals"]["code33"] is True
    validate_bundle(updated)
    automatic = deepcopy(updated)
    automatic["sections"]["TEST"]["quarterly_fundamentals"] = {
        **evaluate_quarters([]),
        "reviewed_previous": deepcopy(packet["quarterly_fundamentals"]),
    }
    validate_bundle(automatic)
    automatic["sections"]["TEST"]["quarterly_fundamentals"]["reviewed_previous"][
        "code33"
    ] = False
    with pytest.raises(ValueError, match="reconcile"):
        validate_bundle(automatic)
    packet["quarterly_fundamentals"]["code33"] = False
    with pytest.raises(ValueError, match="reconcile"):
        validate_bundle(updated)


def test_changed_consolidation_scope_is_not_a_growth_pass():
    rows = quarters()
    rows[-1]["scope_basis"] = "subsidiary disposed"
    result = evaluate_quarters(rows)
    assert result["status"] == "incomparable"
    assert result["code33"] is None
