"""On-demand, source-labelled company research and deterministic valuation."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from src.gemini_client import generate_grounded_structured
from src.persistent_cache import repo_state_cache

RESEARCH_CACHE_SECONDS = 24 * 60 * 60
_CACHE = repo_state_cache("company_research")


def build_company_research(
    ticker: str,
    info: dict[str, Any],
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Build a screen-grade research packet without fabricating missing inputs."""

    normalized = ticker.strip().upper()
    if not force_refresh:
        cached = _CACHE.read(
            normalized,
            fresh_seconds=RESEARCH_CACHE_SECONDS,
            stale_seconds=RESEARCH_CACHE_SECONDS,
        )
        if cached.status == "fresh" and isinstance(cached.payload.get("context"), dict):
            context = dict(cached.payload["context"])
            context["cache_status"] = "persistent_cache"
            return context

    market = "JP" if normalized.endswith(".T") else "US"
    profile = _profile_key(info)
    research = _grounded_filings_research(normalized, info, market)
    valuation = build_equity_valuation(info, profile=profile)
    warnings = list(valuation.get("warnings") or [])
    warnings.extend(research.get("warnings") or [])
    if research.get("status") != "available":
        warnings.append(
            "一次資料の構造化分析が不完全なため、数値評価と資料分析を分けて確認してください。"
        )
    context = {
        "ticker": normalized,
        "company_name": str(info.get("name") or normalized),
        "market": market,
        "status": "available"
        if valuation.get("status") == "available"
        or research.get("status") == "available"
        else "unavailable",
        "readiness": valuation.get("readiness", "not-decision-ready"),
        "valuation": valuation,
        "segments": research.get("segments", []),
        "guidance": research.get("guidance", []),
        "catalysts": research.get("catalysts", []),
        "risks": research.get("risks", []),
        "outlook": research.get("outlook", ""),
        "sources": research.get("sources", []),
        "warnings": list(dict.fromkeys(warnings)),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cache_status": "live",
        "model": research.get("model", ""),
        "usage": research.get("usage", {}),
    }
    if context["status"] == "available":
        _CACHE.write(normalized, {"context": context}, fetched_at=context["fetched_at"])
    return context


def build_equity_valuation(
    info: dict[str, Any], *, profile: str = "general"
) -> dict[str, Any]:
    """Choose an auditable equity method and return bear/base/bull cases."""

    current_price = _number(info.get("current_price"))
    shares = _number(info.get("share_outstanding"))
    if shares is None:
        market_cap = _number(info.get("market_cap"))
        if market_cap is not None and current_price is not None and current_price > 0:
            shares = market_cap / current_price
    cash = _number(info.get("totalCash"), allow_negative=True) or 0.0
    debt = _number(info.get("totalDebt"), allow_negative=True) or 0.0
    net_debt = debt - cash

    if profile in {"bank", "insurance"}:
        result = _residual_income_valuation(
            info,
            current_price=current_price,
        )
    elif profile == "reit":
        result = _reit_valuation(info, current_price=current_price, shares=shares)
    else:
        result = _dcf_valuation(
            info,
            current_price=current_price,
            shares=shares,
            net_debt=net_debt,
        )
    result["profile"] = profile
    result["current_price"] = current_price
    currency = str(info.get("currency") or "").upper()
    result["currency"] = currency
    result["current_price_display"] = _money(current_price, currency)
    result["base_value_display"] = _money(result.get("base_value"), currency)
    for case in result.get("cases", []):
        if isinstance(case, dict):
            case["value_display"] = _money(case.get("value"), currency)
    return result


def calculate_dcf(
    *,
    starting_fcf: float,
    growth_rate: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares: float,
    years: int = 5,
) -> float | None:
    """Return FCFF DCF value per share, or None for invalid economics."""

    if (
        starting_fcf <= 0
        or shares <= 0
        or years <= 0
        or wacc <= terminal_growth
        or wacc <= 0
    ):
        return None
    present_value = 0.0
    fcf = starting_fcf
    for year in range(1, years + 1):
        fcf *= 1 + growth_rate
        present_value += fcf / ((1 + wacc) ** year)
    terminal_value = fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    enterprise_value = present_value + terminal_value / ((1 + wacc) ** years)
    equity_value = enterprise_value - net_debt
    return equity_value / shares if equity_value > 0 else None


def calculate_sotp(
    segments: list[dict[str, Any]], *, net_debt: float, shares: float
) -> dict[str, Any]:
    """Value independently supported segment metrics and multiples."""

    valued = []
    enterprise_value = 0.0
    for item in segments:
        metric = _number(item.get("metric"))
        multiple = _number(item.get("multiple"))
        if metric is None or multiple is None:
            continue
        value = metric * multiple
        enterprise_value += value
        valued.append({**item, "enterprise_value": value})
    equity_value = enterprise_value - net_debt
    per_share = (
        equity_value / shares if valued and shares > 0 and equity_value > 0 else None
    )
    return {
        "status": "available" if per_share is not None else "unavailable",
        "segments": valued,
        "enterprise_value": enterprise_value if valued else None,
        "equity_value": equity_value if valued else None,
        "per_share": per_share,
    }


def _dcf_valuation(
    info: dict[str, Any],
    *,
    current_price: float | None,
    shares: float | None,
    net_debt: float,
) -> dict[str, Any]:
    fcf = _number(info.get("freeCashflow"), allow_negative=True)
    growth = _percent(info.get("revenueGrowth"))
    if fcf is None or fcf <= 0 or shares is None:
        return _unavailable_valuation(
            "簡易FCF DCF",
            "正のフリーキャッシュフローまたは希薄化後株式数が不足しています。",
        )
    base_growth = min(max(growth if growth is not None else 0.05, -0.02), 0.15)
    cases = (
        ("bear", "弱気", max(base_growth - 0.04, -0.05), 0.10, 0.01),
        ("base", "基本", base_growth, 0.09, 0.02),
        ("bull", "強気", min(base_growth + 0.04, 0.20), 0.08, 0.03),
    )
    outputs = []
    for key, label, case_growth, wacc, terminal_growth in cases:
        value = calculate_dcf(
            starting_fcf=fcf,
            growth_rate=case_growth,
            wacc=wacc,
            terminal_growth=terminal_growth,
            net_debt=net_debt,
            shares=shares,
        )
        outputs.append(
            _case_payload(
                key,
                label,
                value,
                current_price,
                {
                    "fcf_growth": case_growth,
                    "wacc": wacc,
                    "terminal_growth": terminal_growth,
                },
            )
        )
    base = next(item for item in outputs if item["key"] == "base")
    reverse_growth = _reverse_dcf_growth(
        target_price=current_price,
        starting_fcf=fcf,
        wacc=0.09,
        terminal_growth=0.02,
        net_debt=net_debt,
        shares=shares,
    )
    sensitivity = [
        {
            "wacc": f"{wacc:.1%}",
            "terminal_growth": f"{terminal:.1%}",
            "value": _money(
                calculate_dcf(
                    starting_fcf=fcf,
                    growth_rate=base_growth,
                    wacc=wacc,
                    terminal_growth=terminal,
                    net_debt=net_debt,
                    shares=shares,
                )
            ),
        }
        for wacc in (0.08, 0.09, 0.10)
        for terminal in (0.01, 0.02, 0.03)
        if wacc > terminal
    ]
    return {
        "status": "available",
        "readiness": "screen-grade",
        "method": "簡易FCF DCF",
        "method_reason": "provider FCFをFCFF proxyとして用いる一般事業会社の簡易評価。",
        "cases": outputs,
        "base_value": base["value"],
        "base_value_display": base["value_display"],
        "discount_label": _discount_label(current_price, base["value"]),
        "reverse_dcf": "算出不可"
        if reverse_growth is None
        else f"現在株価は今後5年のFCF成長率 約{reverse_growth:.1%}を示唆",
        "sensitivity": sensitivity,
        "warnings": [
            "provider FCFは厳密なunlevered FCFFではなくproxyです。",
            "成長率・WACC・永久成長率は公開指標から作るscreen-grade仮定です。",
            "理論値は株価の下限・上限を保証しません。",
        ],
    }


def _residual_income_valuation(
    info: dict[str, Any], *, current_price: float | None
) -> dict[str, Any]:
    book_per_share = _number(info.get("bookValue"))
    roe = _percent(info.get("returnOnEquity"))
    if book_per_share is None or roe is None:
        return _unavailable_valuation(
            "残余利益法", "1株純資産またはROEが不足しています。"
        )
    outputs = []
    for key, label, roe_shift, cost, growth in (
        ("bear", "弱気", -0.03, 0.10, 0.01),
        ("base", "基本", 0.0, 0.09, 0.02),
        ("bull", "強気", 0.03, 0.08, 0.03),
    ):
        case_roe = max(roe + roe_shift, -0.20)
        value = book_per_share + book_per_share * (case_roe - cost) / (cost - growth)
        value = value if value > 0 else None
        outputs.append(
            _case_payload(
                key,
                label,
                value,
                current_price,
                {"roe": case_roe, "cost_of_equity": cost, "growth": growth},
            )
        )
    base = next(item for item in outputs if item["key"] == "base")
    return {
        "status": "available",
        "readiness": "screen-grade",
        "method": "残余利益法",
        "method_reason": "金融業はFCF DCFより純資産とROEを中心に評価。",
        "cases": outputs,
        "base_value": base["value"],
        "base_value_display": base["value_display"],
        "discount_label": _discount_label(current_price, base["value"]),
        "reverse_dcf": "現在株価との比較はP/B・持続ROEの前提で確認",
        "sensitivity": [],
        "warnings": ["規制資本、信用コスト、配当可能利益は追加確認が必要です。"],
    }


def _reit_valuation(
    info: dict[str, Any], *, current_price: float | None, shares: float | None
) -> dict[str, Any]:
    affo = _number(info.get("affo"), allow_negative=True)
    ffo = _number(info.get("ffo"), allow_negative=True)
    cash_flow = affo if affo is not None else ffo
    if cash_flow is None or cash_flow <= 0 or shares is None:
        return _unavailable_valuation(
            "FFO/AFFO倍率", "REIT評価に必要なFFO/AFFOまたは株式数が不足しています。"
        )
    per_share = cash_flow / shares
    outputs = [
        _case_payload(
            key, label, per_share * multiple, current_price, {"multiple": multiple}
        )
        for key, label, multiple in (
            ("bear", "弱気", 10.0),
            ("base", "基本", 14.0),
            ("bull", "強気", 18.0),
        )
    ]
    base = outputs[1]
    return {
        "status": "available",
        "readiness": "screen-grade",
        "method": "FFO/AFFO倍率",
        "method_reason": "REITの分配可能キャッシュフローを中心に評価。",
        "cases": outputs,
        "base_value": base["value"],
        "base_value_display": base["value_display"],
        "discount_label": _discount_label(current_price, base["value"]),
        "reverse_dcf": "算出対象外",
        "sensitivity": [],
        "warnings": ["NAV、物件鑑定価値、負債満期は別途確認が必要です。"],
    }


def _grounded_filings_research(
    ticker: str, info: dict[str, Any], market: str
) -> dict[str, Any]:
    company = str(info.get("name") or ticker)
    website = str(info.get("website") or "")
    prompt = f"""
上場企業 {company} ({ticker}, {market}) の最新の決算発表、会社見通し、法定開示、
公式IR資料だけを調査してください。SEC/EDGAR、EDINET、JPX、会社公式IRを優先し、
報道記事やブログを事実の根拠にしないでください。公式サイト候補: {website or "不明"}。
事業・地域・製品セグメントごとに、開示された売上、利益、利益率、成長要因、弱点を整理し、
数値は資料記載の単位に揃えて unit（例: USD million、百万円）を明記し、利益率は百分率で返してください。
非開示なら数値を null としてください。会社見通し、カタリスト、リスク、半年から2年の条件付き見通しを、
事実と解釈を混同せず日本語で返してください。各項目の source_url と outlook_source_url は
検索引用に実在するURLだけを使ってください。
"""
    generated = generate_grounded_structured(prompt, _research_schema())
    if generated.get("status") != "available":
        return {
            "status": str(generated.get("status") or "unavailable"),
            "segments": [],
            "guidance": [],
            "catalysts": [],
            "risks": [],
            "outlook": "",
            "sources": [],
            "warnings": [
                str(generated.get("error") or "一次資料分析を利用できません。")
            ],
            "model": str(generated.get("model") or ""),
            "usage": {},
        }
    citations = {
        _canonical_url(str(item.get("url") or "")): item
        for item in generated.get("citations", [])
        if _canonical_url(str(item.get("url") or ""))
    }
    official_domain = urlparse(website).netloc.lower().removeprefix("www.")
    allowed_domains = {
        "sec.gov",
        "edinet-fsa.go.jp",
        "jpx.co.jp",
    }
    if official_domain:
        allowed_domains.add(official_domain)
    data = generated.get("data") or {}
    sources = []
    for url, citation in citations.items():
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if any(
            host == domain or host.endswith(f".{domain}") for domain in allowed_domains
        ):
            sources.append(
                {
                    "url": url,
                    "title": str(citation.get("title") or url),
                    "source_type": "primary",
                }
            )
    allowed_urls = {item["url"] for item in sources}
    segments = _validated_evidence_rows(data.get("segments"), allowed_urls)
    guidance = _validated_evidence_rows(data.get("guidance"), allowed_urls)
    catalysts = _validated_evidence_rows(data.get("catalysts"), allowed_urls)
    risks = _validated_evidence_rows(data.get("risks"), allowed_urls)
    outlook_url = _canonical_url(str(data.get("outlook_source_url") or ""))
    outlook = str(data.get("outlook") or "") if outlook_url in allowed_urls else ""
    has_grounded_content = bool(segments or guidance or catalysts or risks or outlook)
    return {
        "status": "available" if sources and has_grounded_content else "partial",
        "segments": segments,
        "guidance": guidance,
        "catalysts": catalysts,
        "risks": risks,
        "outlook": outlook,
        "sources": sources,
        "warnings": list(generated.get("warnings") or [])
        + ([] if sources else ["公式一次資料の検索引用を検証できませんでした。"])
        + (
            ["条件付き見通しの一次資料URLを検証できなかったため表示しません。"]
            if data.get("outlook") and not outlook
            else []
        ),
        "model": str(generated.get("model") or ""),
        "usage": {
            "total_tokens": int(generated.get("total_tokens") or 0),
            "search_queries": int(generated.get("search_query_count") or 0),
        },
    }


def _research_schema() -> dict[str, Any]:
    evidence = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "summary": {"type": "string"},
            "revenue": {"type": ["number", "null"]},
            "operating_profit": {"type": ["number", "null"]},
            "margin": {"type": ["number", "null"]},
            "period": {"type": "string"},
            "unit": {"type": "string"},
            "source_url": {"type": "string"},
        },
        "required": ["name", "summary", "source_url"],
    }
    return {
        "type": "object",
        "properties": {
            "segments": {"type": "array", "items": evidence},
            "guidance": {"type": "array", "items": evidence},
            "catalysts": {"type": "array", "items": evidence},
            "risks": {"type": "array", "items": evidence},
            "outlook": {"type": "string"},
            "outlook_source_url": {"type": "string"},
        },
        "required": [
            "segments",
            "guidance",
            "catalysts",
            "risks",
            "outlook",
            "outlook_source_url",
        ],
    }


def _validated_evidence_rows(
    value: Any, allowed_urls: set[str]
) -> list[dict[str, Any]]:
    rows = []
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            continue
        url = _canonical_url(str(raw.get("source_url") or ""))
        if not url or url not in allowed_urls:
            continue
        rows.append({**raw, "source_url": url})
    return rows


def _case_payload(
    key: str,
    label: str,
    value: float | None,
    current_price: float | None,
    assumptions: dict[str, float],
) -> dict[str, Any]:
    upside = (
        ((value / current_price) - 1) * 100
        if value is not None and current_price is not None and current_price > 0
        else None
    )
    return {
        "key": key,
        "label": label,
        "value": value,
        "value_display": _money(value),
        "upside": upside,
        "upside_display": "-" if upside is None else f"{upside:+.1f}%",
        "assumptions": assumptions,
        "assumptions_display": " / ".join(
            f"{name} {number:.1%}" if number < 1 else f"{name} {number:.1f}x"
            for name, number in assumptions.items()
        ),
    }


def _reverse_dcf_growth(
    *,
    target_price: float | None,
    starting_fcf: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares: float,
) -> float | None:
    if target_price is None or target_price <= 0:
        return None
    low, high = -0.20, 0.50
    for _ in range(70):
        middle = (low + high) / 2
        value = calculate_dcf(
            starting_fcf=starting_fcf,
            growth_rate=middle,
            wacc=wacc,
            terminal_growth=terminal_growth,
            net_debt=net_debt,
            shares=shares,
        )
        if value is None:
            return None
        if value < target_price:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def _profile_key(info: dict[str, Any]) -> str:
    text = " ".join(str(info.get(key) or "") for key in ("sector", "industry")).lower()
    if any(word in text for word in ("bank", "銀行")):
        return "bank"
    if any(word in text for word in ("insurance", "保険")):
        return "insurance"
    if any(word in text for word in ("reit", "real estate investment trust")):
        return "reit"
    return "general"


def _unavailable_valuation(method: str, reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "readiness": "not-decision-ready",
        "method": method,
        "method_reason": reason,
        "cases": [],
        "base_value": None,
        "base_value_display": "算出不可",
        "discount_label": "判定不能",
        "reverse_dcf": "算出不可",
        "sensitivity": [],
        "warnings": [reason],
    }


def _discount_label(current: float | None, base: float | None) -> str:
    if current is None or base is None or current <= 0:
        return "判定不能"
    if current < base * 0.9:
        return "割安候補"
    if current > base * 1.1:
        return "割高候補"
    return "適正圏"


def _percent(value: Any) -> float | None:
    number = _number(value, allow_negative=True)
    if number is None:
        return None
    # StockInfo normalizes growth and return ratios to percentage points.
    # Keep even sub-1% values unambiguous (0.5 means 0.5%, not 50%).
    return number / 100


def _number(value: Any, *, allow_negative: bool = False) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or (not allow_negative and number <= 0):
        return None
    return number


def _money(value: float | None, currency: str = "") -> str:
    if value is None:
        return "算出不可"
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{value:,.2f}"


def _canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return parsed._replace(fragment="").geturl()
