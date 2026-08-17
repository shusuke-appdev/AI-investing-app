from src.services.analysis_context import DataResult
from src.services.data_fetch_manifest import (
    get_data_fetch_manifest,
    required_data_names,
    requirement_failures,
)


def test_data_fetch_manifest_declares_option_horizon_dependency():
    rows = get_data_fetch_manifest("market_options")

    assert rows
    assert rows[0]["name"] == "index_option_horizons"
    assert rows[0]["required"] is True
    assert "1W" in rows[0]["notes"]
    assert "1M" in rows[0]["notes"]
    assert required_data_names("market_options") == ["index_option_horizons"]


def test_required_manifest_reports_missing_and_degraded_statuses():
    assert requirement_failures("stock_analysis", []) == [
        "price_history_profile: required status missing (stock_profile, price_history)"
    ]

    failures = requirement_failures(
        "stock_analysis",
        [
            DataResult(name="stock_profile", is_partial=True),
            DataResult(name="price_history"),
        ],
    )

    assert failures == [
        "price_history_profile: required dependency degraded (stock_profile)"
    ]


def test_theme_leader_manifest_declares_rank_price_and_benchmark_contracts():
    rows = get_data_fetch_manifest("theme_leader_discovery")

    assert [row["name"] for row in rows] == [
        "theme_rankings",
        "candidate_ohlcv",
        "market_benchmark",
        "gemini_external_universe",
        "fundamental_profiles",
    ]
    assert all(row["required"] for row in rows[:3])
    assert all(not row["required"] for row in rows[3:])
    assert all(row["max_stale_seconds"] == 12 * 60 * 60 for row in rows[:3])
    assert rows[3]["max_stale_seconds"] == 24 * 60 * 60
    assert "40" in rows[1]["notes"]
    assert "same batch" in rows[2]["notes"]


def test_comprehensive_theme_ranking_manifest_declares_one_batch_and_no_zero_fill():
    rows = get_data_fetch_manifest("theme_ranking")

    assert [row["name"] for row in rows] == [
        "measurement_ohlcv",
        "market_benchmark",
    ]
    assert all(row["required"] for row in rows)
    assert "one batch" in rows[0]["notes"]
    assert "zero-fill" in rows[0]["fallback"]
