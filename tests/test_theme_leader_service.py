from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.persistent_cache import PersistentCacheRead
from src.provider_result import FetchResult
from src.services import theme_leader_service as service


def _frame(
    *,
    rows: int = 260,
    daily_growth: float = 0.002,
    final_jump: float = 0.0,
    final_volume: float = 5_000_000,
) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=rows)
    close = 50 * np.power(1 + daily_growth, np.arange(rows))
    close[-1] *= 1 + final_jump
    volume = np.full(rows, 5_000_000.0)
    volume[-1] = final_volume
    return pd.DataFrame(
        {
            "Open": close * 0.998,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": volume,
        },
        index=index,
    )


def _ranking(theme: str = "AI半導体", rank: int = 1) -> dict:
    return {
        "theme": theme,
        "rank": rank,
        "rank_1w": rank,
        "rank_1m": rank + 2,
        "rank_6m": rank + 8,
        "rank_acceleration": 8,
        "coverage_1w": 1.0,
        "coverage_1m": 1.0,
        "coverage_6m": 1.0,
        "performance_1w": 4.0,
        "performance_1m": 10.0,
        "performance_6m": 35.0,
    }


def test_select_candidate_themes_unions_top_three_and_accelerators():
    rows = [_ranking(f"T{rank}", rank) for rank in range(1, 8)]
    rows[5]["rank_acceleration"] = 20
    rows[6]["rank_acceleration"] = 15

    selected = service.select_candidate_themes(rows)

    assert [row["theme"] for row in selected] == ["T1", "T2", "T3", "T6", "T7"]


def test_theme_with_missing_period_coverage_is_not_selected():
    missing = _ranking()
    missing["coverage_1m"] = None

    assert service.select_candidate_themes([missing]) == []


def test_build_discovery_finds_breakout_candidate_without_zero_filling(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_themes",
        lambda market: {"AI半導体": ["LEAD", "PEER"]},
    )
    context = service.build_theme_leader_discovery(
        market_type="US",
        ranking_rows=[_ranking()],
        price_frames={
            "LEAD": _frame(final_jump=0.015, final_volume=10_000_000),
            "PEER": _frame(daily_growth=0.001),
        },
        benchmark_frame=_frame(daily_growth=0.0004),
        fetched_at="2026-08-17T00:00:00+00:00",
    )

    assert context["status"] == "available"
    candidate = context["candidates"][0]
    assert candidate["ticker"] == "LEAD"
    assert candidate["status"] == "ブレイク確認"
    assert candidate["stage_pass_count"] == 7
    assert candidate["market_relative_20d"] > 0
    assert candidate["market_relative_63d"] > 0
    assert candidate["theme_relative_20d"] > 0
    assert candidate["rvol"] == pytest.approx(2.0)
    assert 0 <= candidate["score"] <= 100
    assert sum(candidate["score_breakdown"].values()) == pytest.approx(
        candidate["score"]
    )


def test_missing_history_and_stale_results_are_excluded_not_scored(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_themes",
        lambda market: {"AI半導体": ["SHORT", "PEER"]},
    )
    kwargs = {
        "market_type": "US",
        "ranking_rows": [_ranking()],
        "price_frames": {
            "SHORT": _frame(rows=120),
            "PEER": _frame(daily_growth=0.001),
        },
        "benchmark_frame": _frame(daily_growth=0.0004),
    }

    short = service.build_theme_leader_discovery(**kwargs)
    stale = service.build_theme_leader_discovery(**kwargs, is_stale=True)

    assert short["candidates"] == []
    assert short["excluded_reasons"]["履歴不足"] == 1
    assert stale["candidates"] == []
    assert stale["status"] == "stale_unavailable"
    assert stale["excluded_reasons"]["古いキャッシュ"] == 2


def test_stage_four_and_four_atr_extension_are_excluded(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_themes",
        lambda market: {"AI半導体": ["DOWN", "HOT", "PEER"]},
    )
    context = service.build_theme_leader_discovery(
        market_type="US",
        ranking_rows=[_ranking()],
        price_frames={
            "DOWN": _frame(daily_growth=-0.002),
            "HOT": _frame(final_jump=0.20, final_volume=10_000_000),
            "PEER": _frame(daily_growth=0.001),
        },
        benchmark_frame=_frame(daily_growth=0.0004),
    )

    assert "DOWN" not in {item["ticker"] for item in context["candidates"]}
    assert "HOT" not in {item["ticker"] for item in context["candidates"]}
    assert (
        context["excluded_reasons"].get("ステージ3/4", 0)
        + context["excluded_reasons"].get("200日線下降", 0)
        >= 1
    )
    assert context["excluded_reasons"]["過熱"] >= 1


def test_duplicate_theme_membership_uses_strongest_theme(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_themes",
        lambda market: {
            "AI半導体": ["LEAD", "PEER1"],
            "データセンター": ["LEAD", "PEER2"],
        },
    )
    second = _ranking("データセンター", 2)
    context = service.build_theme_leader_discovery(
        market_type="US",
        ranking_rows=[_ranking(), second],
        price_frames={
            "LEAD": _frame(final_jump=0.015, final_volume=10_000_000),
            "PEER1": _frame(daily_growth=0.001),
            "PEER2": _frame(daily_growth=0.0008),
        },
        benchmark_frame=_frame(daily_growth=0.0004),
    )

    candidate = next(item for item in context["candidates"] if item["ticker"] == "LEAD")
    assert candidate["primary_theme"] == "AI半導体"
    assert set(candidate["themes"]) == {"AI半導体", "データセンター"}


@pytest.mark.parametrize(
    ("passes", "distance", "rvol", "expected"),
    [
        (6, -8.0, 1.0, "ステージ2移行待ち"),
        (7, -3.0, 1.0, "ブレイク準備"),
        (7, 1.0, 1.5, "ブレイク確認"),
        (7, 1.0, 1.4, ""),
    ],
)
def test_candidate_status_boundaries(passes, distance, rvol, expected):
    assert service._candidate_status(passes, distance, rvol) == expected


def test_jp_discovery_uses_japan_benchmark(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_themes",
        lambda market: {"半導体": ["1111.T", "2222.T"]},
    )
    context = service.build_theme_leader_discovery(
        market_type="JP",
        ranking_rows=[_ranking("半導体")],
        price_frames={
            "1111.T": _frame(final_jump=0.015, final_volume=10_000_000),
            "2222.T": _frame(daily_growth=0.001),
        },
        benchmark_frame=_frame(daily_growth=0.0004),
    )

    assert context["benchmark"] == "1306.T"
    assert context["candidates"]


def test_live_discovery_uses_one_candidate_price_batch(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service,
        "get_themes",
        lambda market: {"AI半導体": ["LEAD", "PEER"]},
    )
    monkeypatch.setattr(
        service,
        "build_trend_ranking_context",
        lambda *args, **kwargs: {"items": [_ranking()], "quality_warnings": []},
    )
    monkeypatch.setattr(
        service,
        "get_theme_measurement_baskets",
        lambda market: {"AI半導体": {"measurement_tickers": ["LEAD", "PEER"]}},
    )
    monkeypatch.setattr(
        service,
        "discover_external_theme_tickers",
        lambda *args, **kwargs: {
            "status": "unavailable",
            "validated": [],
            "unverified": [],
            "warnings": [],
            "excluded_reasons": {},
        },
    )
    monkeypatch.setattr(
        service,
        "enrich_theme_leader_fundamentals",
        lambda context, **kwargs: context,
    )
    raw = pd.concat(
        {
            "LEAD": _frame(final_jump=0.015, final_volume=10_000_000),
            "PEER": _frame(daily_growth=0.001),
            "SPY": _frame(daily_growth=0.0004),
        },
        axis=1,
    )

    def fake_download(tickers, **kwargs):
        calls.append((list(tickers), kwargs))
        return raw

    monkeypatch.setattr(service.yf, "download", fake_download)

    result = service._build_live_discovery("US")

    assert result.is_available
    assert len(calls) == 1
    assert calls[0][0] == ["LEAD", "PEER", "SPY"]
    assert calls[0][1]["period"] == "2y"
    assert len(calls[0][0]) <= service.MAX_UNIVERSE_TICKERS + 1


def test_partial_fetch_keeps_valid_candidate_and_warns(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_themes",
        lambda market: {"AI半導体": ["LEAD", "PEER", "MISSING"]},
    )
    context = service.build_theme_leader_discovery(
        market_type="US",
        ranking_rows=[_ranking()],
        price_frames={
            "LEAD": _frame(final_jump=0.015, final_volume=10_000_000),
            "PEER": _frame(daily_growth=0.001),
        },
        benchmark_frame=_frame(daily_growth=0.0004),
        is_partial=True,
    )

    assert context["status"] == "partial"
    assert context["candidates"]
    assert context["fetched_count"] == 2
    assert any("一部銘柄" in warning for warning in context["warnings"])


def test_setup_score_rewards_vcp_contraction_pivot_and_volume():
    row = _ranking()
    score = service._score_candidate(
        row=row,
        pass_count=7,
        market_rs={"20d": 1.0, "63d": 2.0},
        theme_rs={"20d": 1.0, "63d": 1.0},
        rs_near_high=True,
        vcp=True,
        atr_contraction=True,
        pivot_distance=-2.0,
        volume_contraction=True,
        rvol=0.8,
    )

    assert score["setup_readiness"] == 20
    assert score["stage2_fit"] == 30
    assert score["relative_strength"] == 25


def test_low_liquidity_is_excluded_before_scoring(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_themes",
        lambda market: {"AI半導体": ["THIN", "PEER"]},
    )
    thin = _frame(final_jump=0.015, final_volume=200)
    thin["Volume"] = 100.0
    context = service.build_theme_leader_discovery(
        market_type="US",
        ranking_rows=[_ranking()],
        price_frames={"THIN": thin, "PEER": _frame(daily_growth=0.001)},
        benchmark_frame=_frame(daily_growth=0.0004),
    )

    assert "THIN" not in {item["ticker"] for item in context["candidates"]}
    assert context["excluded_reasons"]["低流動性"] == 1


def test_fundamental_enrichment_separates_main_pending_and_weak(monkeypatch):
    candidates = [
        {
            "ticker": ticker,
            "score": technical,
            "stage_pass_count": 7,
            "market_relative_63d": technical,
            "candidate_source": "登録代表",
        }
        for ticker, technical in (
            ("GOOD", 80),
            ("TECH", 90),
            ("WEAK", 95),
            ("WAIT", 85),
        )
    ]
    profiles = {
        "GOOD": (
            {"name": "Good"},
            {"score": 60, "coverage": 0.8, "status": "available", "summary": "ok"},
            "",
        ),
        "TECH": (
            {"name": "Tech"},
            {"score": 45, "coverage": 0.8, "status": "available", "summary": "ok"},
            "",
        ),
        "WEAK": (
            {"name": "Weak"},
            {"score": 35, "coverage": 0.8, "status": "available", "summary": "weak"},
            "",
        ),
        "WAIT": (
            {"name": "Wait"},
            {
                "score": None,
                "coverage": 0.4,
                "status": "unavailable",
                "summary": "missing",
            },
            "",
        ),
    }
    monkeypatch.setattr(
        service,
        "_fetch_fundamental",
        lambda ticker, market: profiles[ticker],
    )
    context = service._empty_context("US", status="available")
    context["candidates"] = candidates

    enriched = service.enrich_theme_leader_fundamentals(context, market_type="US")

    assert [item["ticker"] for item in enriched["candidates"]] == ["TECH", "GOOD"]
    assert enriched["candidates"][0]["fundamental_category"] == "技術先行"
    assert enriched["candidates"][1]["fundamental_category"] == "研究優先"
    assert [item["ticker"] for item in enriched["fundamental_pending"]] == ["WAIT"]
    assert enriched["excluded_reasons"]["ファンダメンタル裏付け不足"] == 1


def test_fundamental_fetch_disables_summary_and_translation(monkeypatch):
    calls = []

    def fake_info(ticker, **kwargs):
        calls.append((ticker, kwargs))
        return {"name": ticker, "market_cap": 10_000_000_000}

    monkeypatch.setattr(service, "get_stock_info", fake_info)
    monkeypatch.setattr(
        service,
        "evaluate_fundamental_profile",
        lambda ticker, info, market_type: {"score": None, "coverage": 0.0},
    )

    service._fetch_fundamental("NVDA", "US")

    assert calls == [
        (
            "NVDA",
            {"include_summary": False, "translate_summary": False},
        )
    ]


def test_fundamental_enrichment_fetches_at_most_fifteen_profiles(monkeypatch):
    calls = []
    context = service._empty_context("US", status="available")
    context["candidates"] = [
        {
            "ticker": f"T{index}",
            "score": 80,
            "stage_pass_count": 7,
            "market_relative_63d": 5,
            "candidate_source": "登録代表",
        }
        for index in range(20)
    ]

    def fake_fetch(ticker, market):
        calls.append(ticker)
        return (
            {"name": ticker},
            {"score": 60, "coverage": 0.8, "status": "available"},
            "",
        )

    monkeypatch.setattr(service, "_fetch_fundamental", fake_fetch)

    service.enrich_theme_leader_fundamentals(context, market_type="US")

    assert len(calls) == service.MAX_FUNDAMENTAL_PROFILES


def test_cache_only_page_read_never_starts_live_discovery(monkeypatch, tmp_path):
    cached = PersistentCacheRead(
        key="US__AI半導体",
        namespace="theme_leader_discovery",
        path=tmp_path / "cache.json",
        status="fresh",
        payload={
            "context": {
                "market_type": "US",
                "status": "available",
                "candidates": [{"ticker": "NVDA"}],
                "warnings": [],
            }
        },
        fetched_at="2026-08-17T00:00:00+00:00",
        age_seconds=10,
    )

    class FakeCache:
        def read(self, *args, **kwargs):
            return cached

    monkeypatch.setattr(service, "_DISCOVERY_CACHE", FakeCache())

    result = service.get_cached_theme_leader_discovery_result("US", ["AI半導体"])

    assert result.data["candidates"][0]["ticker"] == "NVDA"
    assert result.source == "persistent_cache"


def test_stale_cached_candidates_are_removed_when_live_refresh_fails(
    monkeypatch, tmp_path
):
    cached = PersistentCacheRead(
        key="US",
        namespace="theme_leader_discovery",
        path=tmp_path / "US.json",
        status="stale",
        payload={
            "context": {
                "market_type": "US",
                "status": "available",
                "candidates": [{"ticker": "OLD"}],
                "excluded_reasons": {},
                "warnings": [],
            }
        },
        fetched_at="2026-08-16T00:00:00+00:00",
        age_seconds=50_000,
    )

    class FakeCache:
        def read(self, *args, **kwargs):
            return cached

    monkeypatch.setattr(service, "_DISCOVERY_CACHE", FakeCache())
    monkeypatch.setattr(
        service,
        "_build_live_discovery",
        lambda market, **kwargs: FetchResult(
            data=service._empty_context(market, status="unavailable"),
            status="unavailable",
            error_code="provider_error",
        ),
    )

    result = service.get_theme_leader_discovery_result("US")

    assert result.is_stale
    assert result.data["candidates"] == []
    assert result.data["status"] == "stale_unavailable"
    assert result.data["excluded_reasons"]["古いキャッシュ"] == 1
