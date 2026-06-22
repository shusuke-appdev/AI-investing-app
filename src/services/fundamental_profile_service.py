"""Adaptive market-cap, style, and sector-aware fundamental scoring."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "fundamental_benchmarks_2026.json"
)

US_LARGE_BOUNDARY = 17_500_000_000
US_MID_BOUNDARY = 5_700_000_000
JP_LARGE_BOUNDARY = 1_000_000_000_000
JP_MID_BOUNDARY = 100_000_000_000
STALE_DAYS = 548

SIZE_LABELS = {"large": "大型", "mid": "中型", "small": "小型"}
STYLE_LABELS = {"growth": "グロース", "value": "バリュー", "blend": "ブレンド"}
PROFILE_LABELS = {
    "general": "一般事業・消費・資本財",
    "software": "SaaS・ソフトウェア",
    "semiconductor": "半導体・ハードウェア",
    "bank": "銀行",
    "insurance": "保険",
    "reit": "REIT",
    "energy_materials": "エネルギー・素材",
    "pharma_biotech": "医薬・バイオ",
    "utilities_telecom": "公益・通信",
}

WEIGHTS = {
    ("large", "growth"): (25, 30, 20, 15, 10),
    ("mid", "growth"): (35, 25, 20, 10, 10),
    ("small", "growth"): (35, 15, 20, 20, 10),
    ("large", "value"): (5, 30, 20, 20, 25),
    ("mid", "value"): (5, 25, 20, 20, 30),
    ("small", "value"): (10, 15, 20, 30, 25),
}
AXES = ("growth", "profitability", "cash", "balance_sheet", "valuation")
AXIS_LABELS = {
    "growth": "成長",
    "profitability": "収益性",
    "cash": "キャッシュ創出",
    "balance_sheet": "財務健全性",
    "valuation": "割安度",
}


def evaluate_fundamental_profile(
    ticker: str,
    info: dict[str, Any] | None,
    *,
    market_type: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Return a transparent adaptive score without turning missing data into zero."""

    values = _derived_values(info or {})
    market = market_type or ("JP" if ticker.upper().endswith(".T") else "US")
    size = classify_market_cap(
        values.get("market_cap"),
        market,
        scale_category=str(values.get("scale_category") or ""),
    )
    sector = select_sector_profile(values)
    benchmarks = load_benchmarks()
    profile_benchmarks = benchmarks["profiles"][sector["key"]]
    style = classify_style(values, size.get("key"), profile_benchmarks)
    stale_days = (
        (today or date.today()) - date.fromisoformat(benchmarks["as_of"])
    ).days
    benchmark_stale = stale_days > STALE_DAYS

    missing_reasons = []
    if size.get("status") != "available":
        missing_reasons.append("時価総額規模を分類できません。")
    if style.get("status") != "available":
        missing_reasons.append(str(style.get("reason") or "スタイルを分類できません。"))
    missing_reasons.extend(_required_kpi_failures(sector["key"], values))

    axis_scores, metric_details, excluded = _axis_scores(
        sector["key"], values, profile_benchmarks, size.get("key")
    )
    coverage = sum(score is not None for score in axis_scores.values()) / len(AXES)
    score = None
    cap_reasons = []
    status = "unavailable"
    weights = _weights(size.get("key"), style.get("key"))
    if not missing_reasons and coverage >= 0.60 and weights:
        usable_weight = sum(
            weights[axis] for axis, value in axis_scores.items() if value is not None
        )
        if usable_weight:
            score = (
                sum(
                    float(value) * weights[axis]
                    for axis, value in axis_scores.items()
                    if value is not None
                )
                / usable_weight
            )
            status = "available" if coverage >= 0.80 else "partial"

    score_cap = 100
    if benchmark_stale:
        score_cap = min(score_cap, 69)
        cap_reasons.append("業種基準が18か月超未更新のため69点上限。")
    if 0.60 <= coverage < 0.80:
        score_cap = min(score_cap, 69)
        cap_reasons.append("データ充足率60～79%の部分評価のため69点上限。")
    if size.get("key") == "small" and (
        _below(axis_scores.get("cash"), 40)
        or _below(axis_scores.get("balance_sheet"), 40)
    ):
        score_cap = min(score_cap, 54)
        cap_reasons.append(
            "小型株のキャッシュ創出または財務健全性が40点未満のため54点上限。"
        )
    if score is not None:
        score = round(min(score, score_cap), 1)

    if score is None and not missing_reasons:
        missing_reasons.append("5評価軸のデータ充足率が60%未満です。")

    return {
        "ticker": ticker.upper(),
        "status": status if score is not None else "unavailable",
        "score": score,
        "score_display": f"{score:.0f}/100" if score is not None else "算出不可",
        "rating": _rating(score),
        "size": size,
        "style": style,
        "sector_profile": sector,
        "axis_scores": {
            axis: {
                "label": AXIS_LABELS[axis],
                "score": value,
                "score_display": f"{value:.0f}" if value is not None else "算出不可",
                "weight": weights.get(axis, 0),
            }
            for axis, value in axis_scores.items()
        },
        "metric_details": metric_details,
        "coverage": round(coverage, 2),
        "coverage_display": f"{coverage:.0%}",
        "missing_reasons": missing_reasons,
        "excluded_metrics": excluded,
        "score_cap": score_cap,
        "cap_reasons": cap_reasons,
        "benchmark": {
            "version": benchmarks["version"],
            "as_of": benchmarks["as_of"],
            "sources": benchmarks["sources"],
            "markets": benchmarks["markets"],
            "is_stale": benchmark_stale,
            "age_days": stale_days,
            "jp_is_proxy": market == "JP",
        },
        "smart_applicability": "growth_proxy"
        if style.get("key") == "growth"
        else "not_applicable",
        "summary": _summary(score, size, style, sector, coverage),
    }


def classify_market_cap(
    market_cap: Any,
    market_type: str,
    *,
    scale_category: str = "",
) -> dict[str, Any]:
    """Classify US names by 2026 Russell ranges and JP names by JPX scale first."""

    market = market_type.upper()
    if market == "JP" and scale_category.strip():
        normalized = scale_category.lower().replace(" ", "")
        if "core30" in normalized or "large70" in normalized:
            key = "large"
        elif "mid400" in normalized:
            key = "mid"
        elif any(token in normalized for token in ("small", "micro")):
            key = "small"
        else:
            key = ""
        if key:
            return {
                "status": "available",
                "key": key,
                "label": SIZE_LABELS[key],
                "borderline": False,
                "source": "J-Quants Scale Category / JPX",
                "as_of": "provider-current",
                "is_proxy": False,
                "scale_category": scale_category,
            }

    value = _number(market_cap)
    if value is None or value <= 0:
        return {"status": "unavailable", "key": "", "label": "分類不能"}
    if market == "JP":
        upper, lower = JP_LARGE_BOUNDARY, JP_MID_BOUNDARY
        source = "JP operating market-cap proxy"
        as_of = "2026-06-23"
        is_proxy = True
    else:
        upper, lower = US_LARGE_BOUNDARY, US_MID_BOUNDARY
        source = "FTSE Russell 2026 indicative market-cap ranges"
        as_of = "2026-04-28"
        is_proxy = False
    key = "large" if value >= upper else "mid" if value >= lower else "small"
    borderline = any(
        boundary * 0.9 <= value <= boundary * 1.1 for boundary in (upper, lower)
    )
    return {
        "status": "available",
        "key": key,
        "label": SIZE_LABELS[key],
        "borderline": borderline,
        "source": source,
        "as_of": as_of,
        "is_proxy": is_proxy,
        "market_cap": value,
    }


def classify_style(
    values: dict[str, Any],
    size_key: str | None,
    benchmarks: dict[str, float],
) -> dict[str, Any]:
    """Classify value/growth/blend from sector-relative factor scores."""

    if size_key not in {"large", "mid", "small"}:
        return {"status": "unavailable", "key": "", "reason": "規模分類がありません。"}
    value_factors = {
        "book_to_price": (_inverse_positive(values.get("price_to_book")), 0.50),
        "forward_earnings_yield": (_inverse_positive(values.get("forward_pe")), 0.30),
        "fcf_yield": (
            _percent_ratio(values.get("free_cashflow"), values.get("market_cap")),
            0.20,
        ),
    }
    value_benchmarks = {
        "book_to_price": _inverse_positive(benchmarks.get("price_to_book")),
        "forward_earnings_yield": _inverse_positive(benchmarks.get("forward_pe")),
        "fcf_yield": benchmarks.get("fcf_yield"),
    }
    growth_multiplier = {"small": 1.25, "mid": 1.0, "large": 0.75}[size_key]
    growth_factors = {
        "revenue_growth": (values.get("revenue_growth"), 0.60),
        "earnings_growth": (values.get("earnings_growth"), 0.40),
    }
    growth_benchmarks = {
        "revenue_growth": _number(
            benchmarks.get("revenue_growth"), allow_negative=True
        ),
        "earnings_growth": _number(
            benchmarks.get("earnings_growth"), allow_negative=True
        ),
    }
    value_score, value_used = _weighted_factor_score(value_factors, value_benchmarks)
    growth_score, growth_used = _weighted_factor_score(
        growth_factors, growth_benchmarks, benchmark_multiplier=growth_multiplier
    )
    available = value_used + growth_used
    coverage = available / 5
    if value_used < 1 or growth_used < 1 or coverage < 0.60:
        return {
            "status": "unavailable",
            "key": "",
            "value_score": value_score,
            "growth_score": growth_score,
            "coverage": round(coverage, 2),
            "reason": "バリュー・グロース双方を含む因子充足率が60%未満です。",
        }
    key = (
        "growth"
        if growth_score - value_score >= 10
        else "value"
        if value_score - growth_score >= 10
        else "blend"
    )
    return {
        "status": "available",
        "key": key,
        "label": STYLE_LABELS[key],
        "value_score": round(value_score, 1),
        "growth_score": round(growth_score, 1),
        "coverage": round(coverage, 2),
        "growth_hurdle_multiplier": growth_multiplier,
        "method": "B/P 50% + forward earnings yield 30% + FCF yield 20%; revenue growth 60% + earnings growth 40%",
        "is_proxy": True,
    }


def select_sector_profile(info: dict[str, Any]) -> dict[str, Any]:
    """Select a business-model profile using industry before broad sector labels."""

    text = " ".join(
        str(info.get(key) or "") for key in ("industry", "sector", "business_profile")
    ).lower()
    mappings = (
        ("bank", ("bank", "banks", "銀行")),
        ("insurance", ("insurance", "insurer", "保険")),
        ("reit", ("reit", "real estate investment trust", "不動産投資信託")),
        ("software", ("software", "saas", "internet", "ソフトウェア")),
        ("semiconductor", ("semiconductor", "hardware", "半導体", "電子部品")),
        (
            "energy_materials",
            (
                "energy",
                "oil",
                "gas",
                "mining",
                "materials",
                "エネルギー",
                "鉱業",
                "素材",
            ),
        ),
        ("pharma_biotech", ("biotech", "pharma", "drug", "医薬", "バイオ")),
        (
            "utilities_telecom",
            (
                "utility",
                "utilities",
                "telecom",
                "communication services",
                "電力",
                "ガス",
                "通信",
            ),
        ),
    )
    for key, tokens in mappings:
        if any(token in text for token in tokens):
            return {"key": key, "label": PROFILE_LABELS[key], "fallback": False}
    return {
        "key": "general",
        "label": PROFILE_LABELS["general"],
        "fallback": bool(text.strip()),
        "warning": "未対応業種のため一般事業プロファイルを暫定適用。"
        if text.strip()
        else "",
    }


@lru_cache(maxsize=1)
def load_benchmarks() -> dict[str, Any]:
    with BENCHMARK_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _axis_scores(
    profile: str,
    values: dict[str, Any],
    benchmarks: dict[str, float],
    size_key: str | None,
) -> tuple[dict[str, float | None], list[dict[str, Any]], list[str]]:
    growth_multiplier = {"small": 1.25, "mid": 1.0, "large": 0.75}.get(
        size_key or "", 1.0
    )
    configs = _profile_metric_configs(profile, values)
    results = {}
    details = []
    excluded = _excluded_metrics(profile)
    for axis in AXES:
        scores = []
        for metric, lower_better, multiplier in configs.get(axis, []):
            actual = _number(values.get(metric), allow_negative=True)
            benchmark = _number(benchmarks.get(metric), allow_negative=True)
            if benchmark is not None and axis == "growth":
                benchmark *= growth_multiplier
            score = _metric_score(actual, benchmark, lower_better=lower_better)
            details.append(
                {
                    "axis": axis,
                    "metric": metric,
                    "actual": actual,
                    "benchmark": benchmark,
                    "score": score,
                    "lower_is_better": lower_better,
                    "weight": multiplier,
                }
            )
            if score is not None:
                scores.append((score, multiplier))
        results[axis] = (
            round(
                sum(score * weight for score, weight in scores)
                / sum(weight for _, weight in scores),
                1,
            )
            if scores
            else None
        )
    return results, details, excluded


def _profile_metric_configs(
    profile: str, values: dict[str, Any]
) -> dict[str, list[tuple[str, bool, float]]]:
    common_growth = [("revenue_growth", False, 0.6), ("earnings_growth", False, 0.4)]
    if profile == "bank":
        return {
            "growth": [
                ("book_value_growth", False, 0.6),
                ("earnings_growth", False, 0.4),
            ],
            "profitability": [("roe", False, 0.5), ("rotce", False, 0.5)],
            "cash": [("cet1", False, 1.0)],
            "balance_sheet": [
                ("cet1", False, 0.6),
                ("nonperforming_assets", True, 0.4),
            ],
            "valuation": [
                ("price_to_book", True, 0.5),
                ("price_to_tangible_book", True, 0.5),
            ],
        }
    if profile == "insurance":
        return {
            "growth": [
                ("book_value_growth", False, 0.6),
                ("earnings_growth", False, 0.4),
            ],
            "profitability": [("roe", False, 0.5), ("combined_ratio", True, 0.5)],
            "cash": [("combined_ratio", True, 1.0)],
            "balance_sheet": [("capital_adequacy", False, 1.0)],
            "valuation": [("price_to_book", True, 1.0)],
        }
    if profile == "reit":
        return {
            "growth": [("ffo_growth", False, 0.5), ("noi_growth", False, 0.5)],
            "profitability": [("occupancy", False, 0.5), ("affo_margin", False, 0.5)],
            "cash": [("payout_ratio", True, 0.5), ("affo_margin", False, 0.5)],
            "balance_sheet": [("net_debt_to_ebitda", True, 1.0)],
            "valuation": [("price_to_affo", True, 0.6), ("nav_premium", True, 0.4)],
        }
    if profile == "software":
        return {
            "growth": common_growth,
            "profitability": [
                ("gross_margin", False, 0.4),
                ("operating_margin", False, 0.3),
                ("rule_of_40", False, 0.3),
            ],
            "cash": [("fcf_margin", False, 1.0)],
            "balance_sheet": [
                ("debt_to_equity", True, 0.5),
                ("current_ratio", False, 0.5),
            ],
            "valuation": [("ev_to_sales", True, 0.5), ("fcf_yield", False, 0.5)],
        }
    if profile == "semiconductor":
        return {
            "growth": common_growth,
            "profitability": [
                ("gross_margin", False, 0.45),
                ("operating_margin", False, 0.35),
                ("roe", False, 0.2),
            ],
            "cash": [("fcf_margin", False, 1.0)],
            "balance_sheet": [
                ("debt_to_equity", True, 0.5),
                ("net_cash_margin", False, 0.5),
            ],
            "valuation": [("forward_pe", True, 0.6), ("fcf_yield", False, 0.4)],
        }
    if profile == "pharma_biotech" and values.get("precommercial_biotech"):
        return {
            "growth": [("pipeline_score", False, 1.0)],
            "profitability": [],
            "cash": [("cash_runway_years", False, 1.0)],
            "balance_sheet": [("net_cash_margin", False, 1.0)],
            "valuation": [],
        }
    base = {
        "growth": common_growth,
        "profitability": [
            ("operating_margin", False, 0.45),
            ("roe", False, 0.35),
            ("gross_margin", False, 0.2),
        ],
        "cash": [("fcf_margin", False, 0.6), ("fcf_yield", False, 0.4)],
        "balance_sheet": [("debt_to_equity", True, 0.6), ("current_ratio", False, 0.4)],
        "valuation": [
            ("forward_pe", True, 0.4),
            ("price_to_book", True, 0.3),
            ("fcf_yield", False, 0.3),
        ],
    }
    if profile == "energy_materials":
        base["profitability"].append(("return_on_invested_capital", False, 0.35))
    if profile == "utilities_telecom":
        base["balance_sheet"].append(("interest_coverage", False, 0.4))
    return base


def _required_kpi_failures(profile: str, values: dict[str, Any]) -> list[str]:
    requirements = {
        "general": (("operating_margin", "roe"),),
        "software": (("revenue_growth",), ("gross_margin", "operating_margin")),
        "semiconductor": (("gross_margin",), ("operating_margin",)),
        "bank": (("roe",), ("price_to_book", "price_to_tangible_book")),
        "insurance": (("roe",), ("price_to_book",)),
        "reit": (("ffo", "affo", "ffo_growth"),),
        "energy_materials": (("free_cashflow", "fcf_margin"),),
        "pharma_biotech": (("pipeline_score", "revenue_growth"),),
        "utilities_telecom": (("roe",), ("debt_to_equity", "interest_coverage")),
    }
    missing = []
    for alternatives in requirements.get(profile, ()):
        if not any(
            _number(values.get(key), allow_negative=True) is not None
            for key in alternatives
        ):
            missing.append(
                f"{PROFILE_LABELS[profile]}の必須KPI（{' / '.join(alternatives)}）が不足。"
            )
    if profile == "pharma_biotech" and values.get("precommercial_biotech"):
        for key in ("cash_runway_years", "pipeline_score"):
            if _number(values.get(key), allow_negative=True) is None:
                missing.append(f"赤字バイオの必須KPI（{key}）が不足。")
    return missing


def _derived_values(info: dict[str, Any]) -> dict[str, Any]:
    values = dict(info)
    aliases = {
        "market_cap": "market_cap",
        "scale_category": "scale_category",
        "revenue_growth": "revenueGrowth",
        "earnings_growth": "earningsGrowth",
        "gross_margin": "grossMargins",
        "operating_margin": "operatingMargins",
        "roe": "returnOnEquity",
        "current_ratio": "currentRatio",
        "debt_to_equity": "debtToEquity",
        "forward_pe": "forward_pe",
        "price_to_book": "priceToBook",
        "free_cashflow": "freeCashflow",
        "total_revenue": "totalRevenue",
        "total_cash": "totalCash",
        "total_debt": "totalDebt",
        "ev_to_sales": "enterpriseToRevenue",
        "industry": "industry",
        "sector": "sector",
    }
    for target, source in aliases.items():
        if values.get(target) is None:
            values[target] = info.get(source)
    values["fcf_margin"] = _percent_ratio(
        values.get("free_cashflow"), values.get("total_revenue")
    )
    values["fcf_yield"] = _percent_ratio(
        values.get("free_cashflow"), values.get("market_cap")
    )
    values["net_cash_margin"] = _percent_ratio(
        (_number(values.get("total_cash"), allow_negative=True) or 0)
        - (_number(values.get("total_debt"), allow_negative=True) or 0),
        values.get("market_cap"),
    )
    if (
        _number(values.get("revenue_growth"), allow_negative=True) is not None
        and _number(values.get("fcf_margin"), allow_negative=True) is not None
    ):
        values["rule_of_40"] = float(values["revenue_growth"]) + float(
            values["fcf_margin"]
        )
    cash = _number(values.get("total_cash"), allow_negative=True)
    fcf = _number(values.get("free_cashflow"), allow_negative=True)
    if cash is not None and fcf is not None and fcf < 0:
        values["cash_runway_years"] = cash / abs(fcf)
    text = f"{values.get('industry', '')} {values.get('sector', '')}".lower()
    values["precommercial_biotech"] = (
        "biotech" in text
        and (_number(values.get("operating_margin"), allow_negative=True) or 0) < 0
    )
    return values


def _weights(size_key: str | None, style_key: str | None) -> dict[str, float]:
    if size_key not in {"large", "mid", "small"} or style_key not in {
        "growth",
        "value",
        "blend",
    }:
        return {}
    if style_key == "blend":
        growth = WEIGHTS[(size_key, "growth")]
        value = WEIGHTS[(size_key, "value")]
        values = tuple(
            (left + right) / 2 for left, right in zip(growth, value, strict=True)
        )
    else:
        values = WEIGHTS[(size_key, style_key)]
    return dict(zip(AXES, values, strict=True))


def _weighted_factor_score(
    factors: dict[str, tuple[Any, float]],
    benchmarks: dict[str, Any],
    *,
    benchmark_multiplier: float = 1.0,
) -> tuple[float, int]:
    scored = []
    for key, (actual, weight) in factors.items():
        benchmark = _number(benchmarks.get(key), allow_negative=True)
        score = _metric_score(
            _number(actual, allow_negative=True),
            benchmark * benchmark_multiplier if benchmark is not None else None,
            lower_better=False,
        )
        if score is not None:
            scored.append((score, weight))
    if not scored:
        return 0.0, 0
    return sum(score * weight for score, weight in scored) / sum(
        weight for _, weight in scored
    ), len(scored)


def _metric_score(
    actual: float | None,
    benchmark: float | None,
    *,
    lower_better: bool,
) -> float | None:
    if actual is None or benchmark is None or benchmark == 0:
        return None
    if actual < 0 < benchmark:
        return 0.0
    ratio = actual / benchmark
    if lower_better:
        if actual <= 0:
            return 100.0
        ratio = benchmark / actual
    return round(max(0.0, min(100.0, (ratio - 0.5) * 100.0)), 1)


def _excluded_metrics(profile: str) -> list[str]:
    if profile == "bank":
        return ["一般企業のD/E", "流動比率", "EV/EBITDA"]
    if profile == "reit":
        return ["通常PER", "EPS成長"]
    if profile == "insurance":
        return ["一般企業のD/E", "流動比率"]
    if profile == "pharma_biotech":
        return ["赤字を欠損扱いする評価"]
    return []


def _rating(score: float | None) -> str:
    if score is None:
        return "算出不可"
    if score >= 70:
        return "優位"
    if score >= 55:
        return "中立"
    return "弱い"


def _summary(
    score: float | None,
    size: dict[str, Any],
    style: dict[str, Any],
    sector: dict[str, Any],
    coverage: float,
) -> str:
    return (
        f"{size.get('label', '分類不能')} / {style.get('label', '分類不能')} / "
        f"{sector.get('label', '未分類')} / "
        f"{f'{score:.0f}点' if score is not None else '算出不可'}（充足率{coverage:.0%}）"
    )


def _below(value: float | None, threshold: float) -> bool:
    return value is not None and value < threshold


def _inverse_positive(value: Any) -> float | None:
    number = _number(value, allow_negative=True)
    return 1 / number if number is not None and number > 0 else None


def _percent_ratio(numerator: Any, denominator: Any) -> float | None:
    top = _number(numerator, allow_negative=True)
    bottom = _number(denominator, allow_negative=True)
    if top is None or bottom in (None, 0):
        return None
    return top / bottom * 100


def _number(value: Any, *, allow_negative: bool = False) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not allow_negative and number <= 0:
        return None
    return number
