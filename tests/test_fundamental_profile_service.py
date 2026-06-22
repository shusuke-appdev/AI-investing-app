from datetime import date

from src.services.fundamental_profile_service import (
    classify_market_cap,
    evaluate_fundamental_profile,
    select_sector_profile,
)


def _software_info(market_cap: float = 30_000_000_000) -> dict:
    return {
        "market_cap": market_cap,
        "sector": "Technology",
        "industry": "Software - Application",
        "revenueGrowth": 22.0,
        "earningsGrowth": 20.0,
        "grossMargins": 78.0,
        "operatingMargins": 28.0,
        "returnOnEquity": 30.0,
        "currentRatio": 2.2,
        "debtToEquity": 5.0,
        "forward_pe": 32.0,
        "priceToBook": 8.0,
        "freeCashflow": 3_000_000_000,
        "totalRevenue": 12_000_000_000,
        "totalCash": 6_000_000_000,
        "totalDebt": 1_000_000_000,
        "enterpriseToRevenue": 6.0,
    }


def test_us_size_boundaries_and_borderline():
    large = classify_market_cap(17_500_000_000, "US")
    mid = classify_market_cap(6_000_000_000, "US")

    assert large["key"] == "large"
    assert large["borderline"] is True
    assert mid["key"] == "mid"
    assert mid["borderline"] is True


def test_jp_scale_category_precedes_market_cap_proxy():
    result = classify_market_cap(10_000_000_000, "JP", scale_category="TOPIX Core30")

    assert result["key"] == "large"
    assert result["is_proxy"] is False


def test_sector_mapping_prevents_bank_and_reit_generic_rules():
    assert select_sector_profile({"industry": "Regional Banks"})["key"] == "bank"
    assert select_sector_profile({"industry": "Retail REIT"})["key"] == "reit"


def test_adaptive_software_score_is_available_with_classification():
    result = evaluate_fundamental_profile("NVDA", _software_info())

    assert result["status"] in {"available", "partial"}
    assert result["size"]["key"] == "large"
    assert result["style"]["key"] in {"growth", "blend", "value"}
    assert result["score"] is not None
    assert result["coverage"] >= 0.6


def test_stale_benchmark_caps_score_at_69():
    result = evaluate_fundamental_profile(
        "TEST",
        _software_info(),
        today=date(2027, 8, 1),
    )

    assert result["benchmark"]["is_stale"] is True
    assert result["score"] <= 69
    assert any("18か月" in reason for reason in result["cap_reasons"])


def test_reit_without_ffo_is_unavailable_and_does_not_use_normal_pe():
    info = _software_info()
    info.update({"industry": "Retail REIT", "sector": "Real Estate"})
    result = evaluate_fundamental_profile("O", info)

    assert result["status"] == "unavailable"
    assert "通常PER" in result["excluded_metrics"]
    assert any("ffo" in reason.lower() for reason in result["missing_reasons"])
