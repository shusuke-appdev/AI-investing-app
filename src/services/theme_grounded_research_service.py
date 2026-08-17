"""Grounded Gemini research for theme-universe expansion and candidate review."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, TypedDict
from urllib.parse import urlparse

from src.constants import GEMINI_MODEL_NAME
from src.gemini_client import (
    GroundedGenerationResult,
    generate_grounded_structured,
)
from src.persistent_cache import repo_state_cache

PROMPT_VERSION = "theme-external-v1"
DEEP_DIVE_PROMPT_VERSION = "theme-deep-dive-v1"
CACHE_SECONDS = 24 * 60 * 60
MAX_PER_THEME = 8
MAX_EXTERNAL_TICKERS = 20
_DISCOVERY_CACHE = repo_state_cache("theme_external_discovery")
_DEEP_DIVE_CACHE = repo_state_cache("theme_candidate_deep_dive")

_PRIMARY_DOMAINS = {
    "sec.gov",
    "www.sec.gov",
    "edinet-fsa.go.jp",
    "disclosure2.edinet-fsa.go.jp",
    "jpx.co.jp",
    "www.jpx.co.jp",
    "nasdaq.com",
    "www.nasdaq.com",
    "nyse.com",
    "www.nyse.com",
}
_ALLOWED_EXCHANGES = {
    "US": {"NASDAQ", "NYSE", "NYSEAMERICAN", "AMEX"},
    "JP": {"TSE", "TOKYO", "JPX"},
}


class GeminiDiscoveredTicker(TypedDict, total=False):
    ticker: str
    exchange: str
    company_name: str
    theme: str
    business_relationship: str
    evidence_date: str
    official_domain: str
    security_type: str
    sources: list[dict[str, str]]


class ValidatedExternalTicker(TypedDict, total=False):
    ticker: str
    exchange: str
    company_name: str
    themes: list[str]
    business_relationship: str
    evidence_date: str
    official_domain: str
    source_urls: list[str]
    source_titles: list[str]
    evidence_quality: int
    validation_status: str


class ExternalThemeDiscoveryContext(TypedDict, total=False):
    status: str
    market_type: str
    themes: list[str]
    validated: list[ValidatedExternalTicker]
    unverified: list[dict[str, Any]]
    excluded_reasons: dict[str, int]
    fetched_at: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    search_query_count: int
    warnings: list[str]
    error: str
    cache_status: str


def discover_external_theme_tickers(
    market_type: str,
    themes: list[str],
    *,
    force_refresh: bool = False,
) -> ExternalThemeDiscoveryContext:
    """Ask Gemini once, then deterministically validate cited evidence."""

    market = market_type.upper()
    normalized_themes = sorted({theme.strip() for theme in themes if theme.strip()})
    key = _cache_key(market, normalized_themes, GEMINI_MODEL_NAME, PROMPT_VERSION)
    if not force_refresh:
        cached = _DISCOVERY_CACHE.read(
            key,
            fresh_seconds=CACHE_SECONDS,
            stale_seconds=CACHE_SECONDS,
        )
        if cached.status == "fresh" and isinstance(cached.payload.get("context"), dict):
            context = dict(cached.payload["context"])
            context["cache_status"] = "persistent_cache"
            return context  # type: ignore[return-value]

    generated = generate_grounded_structured(
        _discovery_prompt(market, normalized_themes),
        _discovery_schema(normalized_themes),
    )
    context = validate_external_discovery(
        market_type=market,
        themes=normalized_themes,
        generated=generated,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    if context["status"] in {"available", "partial"}:
        _DISCOVERY_CACHE.write(
            key,
            {"context": context},
            fetched_at=context["fetched_at"],
        )
    return context


def validate_external_discovery(
    *,
    market_type: str,
    themes: list[str],
    generated: GroundedGenerationResult,
    fetched_at: str,
    today: date | None = None,
) -> ExternalThemeDiscoveryContext:
    """Validate model output without accepting uncited URLs or model scores."""

    citation_lookup = {
        _canonical_url(str(item.get("url") or "")): item
        for item in generated.get("citations", [])
        if _canonical_url(str(item.get("url") or ""))
    }
    raw_candidates = generated.get("data", {}).get("candidates", [])
    if not isinstance(raw_candidates, list):
        raw_candidates = []
    excluded: Counter[str] = Counter()
    unverified: list[dict[str, Any]] = []
    verified_by_ticker: dict[str, ValidatedExternalTicker] = {}
    cutoff = (today or date.today()) - timedelta(days=548)
    per_theme: Counter[str] = Counter()

    for raw in raw_candidates:
        candidate = dict(raw) if isinstance(raw, dict) else {}
        reason = _candidate_validation_reason(
            candidate,
            market_type=market_type,
            allowed_themes=set(themes),
            citation_lookup=citation_lookup,
            cutoff=cutoff,
        )
        ticker = _normalize_ticker(str(candidate.get("ticker") or ""), market_type)
        if reason:
            excluded[reason] += 1
            unverified.append(
                {
                    "ticker": ticker or str(candidate.get("ticker") or ""),
                    "theme": str(candidate.get("theme") or ""),
                    "company_name": str(candidate.get("company_name") or ""),
                    "reason": reason,
                    "source_urls": _cited_source_urls(candidate, citation_lookup),
                }
            )
            continue
        theme = str(candidate["theme"])
        if per_theme[theme] >= MAX_PER_THEME:
            excluded["テーマ別上限"] += 1
            continue
        per_theme[theme] += 1
        urls = _cited_source_urls(candidate, citation_lookup)
        titles = [str(citation_lookup[url].get("title") or "") for url in urls]
        existing = verified_by_ticker.get(ticker)
        if existing:
            if theme not in existing["themes"]:
                existing["themes"].append(theme)
            existing["source_urls"] = list(
                dict.fromkeys([*existing["source_urls"], *urls])
            )
            existing["source_titles"] = list(
                dict.fromkeys([*existing["source_titles"], *titles])
            )
            existing["evidence_quality"] = len(existing["source_urls"])
            continue
        verified_by_ticker[ticker] = {
            "ticker": ticker,
            "exchange": str(candidate.get("exchange") or "").upper(),
            "company_name": str(candidate.get("company_name") or ""),
            "themes": [theme],
            "business_relationship": str(candidate.get("business_relationship") or ""),
            "evidence_date": str(candidate.get("evidence_date") or ""),
            "official_domain": str(candidate.get("official_domain") or ""),
            "source_urls": urls,
            "source_titles": titles,
            "evidence_quality": len(urls),
            "validation_status": "source_verified",
        }

    validated = _round_robin_external(list(verified_by_ticker.values()), themes)
    generated_status = str(generated.get("status") or "unavailable")
    status = "available" if validated else "partial" if unverified else generated_status
    warnings = list(generated.get("warnings") or [])
    if generated_status != "available" and generated.get("error"):
        warnings.append("Gemini探索を利用できないため、登録代表銘柄だけで続行します。")
    return {
        "status": status,
        "market_type": market_type,
        "themes": themes,
        "validated": validated,
        "unverified": unverified,
        "excluded_reasons": dict(sorted(excluded.items())),
        "fetched_at": fetched_at,
        "model": str(generated.get("model") or GEMINI_MODEL_NAME),
        "input_tokens": int(generated.get("input_tokens") or 0),
        "output_tokens": int(generated.get("output_tokens") or 0),
        "total_tokens": int(generated.get("total_tokens") or 0),
        "search_query_count": int(generated.get("search_query_count") or 0),
        "warnings": list(dict.fromkeys(warnings)),
        "error": str(generated.get("error") or ""),
        "cache_status": "live",
    }


def deep_dive_theme_candidates(
    market_type: str,
    candidates: list[dict[str, Any]],
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Research up to five already-ranked candidates without changing ranks."""

    selected = [
        {
            "ticker": str(item.get("ticker") or ""),
            "theme": str(item.get("primary_theme") or ""),
        }
        for item in candidates[:5]
        if item.get("ticker")
    ]
    key = _cache_key(
        market_type.upper(),
        [f"{item['ticker']}:{item['theme']}" for item in selected],
        GEMINI_MODEL_NAME,
        DEEP_DIVE_PROMPT_VERSION,
    )
    if not force_refresh:
        cached = _DEEP_DIVE_CACHE.read(
            key,
            fresh_seconds=CACHE_SECONDS,
            stale_seconds=CACHE_SECONDS,
        )
        if cached.status == "fresh" and isinstance(cached.payload.get("context"), dict):
            context = dict(cached.payload["context"])
            context["cache_status"] = "persistent_cache"
            return context
    generated = generate_grounded_structured(
        _deep_dive_prompt(market_type.upper(), selected),
        _deep_dive_schema(),
    )
    cited = {
        _canonical_url(str(item.get("url") or ""))
        for item in generated.get("citations", [])
    }
    raw_items = generated.get("data", {}).get("items", [])
    items = []
    allowed = {item["ticker"] for item in selected}
    for raw in raw_items if isinstance(raw_items, list) else []:
        item = dict(raw) if isinstance(raw, dict) else {}
        ticker = _normalize_ticker(str(item.get("ticker") or ""), market_type)
        urls = [
            url
            for url in (
                _canonical_url(str(value)) for value in item.get("source_urls", [])
            )
            if url and url in cited
        ]
        if ticker not in allowed or not urls:
            continue
        item["ticker"] = ticker
        item["source_urls"] = list(dict.fromkeys(urls))
        items.append(item)
    context = {
        "status": "available"
        if items
        else str(generated.get("status") or "unavailable"),
        "items": items,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "model": generated.get("model", GEMINI_MODEL_NAME),
        "input_tokens": int(generated.get("input_tokens") or 0),
        "output_tokens": int(generated.get("output_tokens") or 0),
        "total_tokens": int(generated.get("total_tokens") or 0),
        "search_query_count": int(generated.get("search_query_count") or 0),
        "warnings": generated.get("warnings", []),
        "error": generated.get("error", ""),
        "cache_status": "live",
    }
    if items:
        _DEEP_DIVE_CACHE.write(
            key, {"context": context}, fetched_at=context["fetched_at"]
        )
    return context


def _candidate_validation_reason(
    candidate: dict[str, Any],
    *,
    market_type: str,
    allowed_themes: set[str],
    citation_lookup: dict[str, dict[str, Any]],
    cutoff: date,
) -> str:
    ticker = _normalize_ticker(str(candidate.get("ticker") or ""), market_type)
    if not ticker:
        return "ティッカー形式不正"
    exchange = str(candidate.get("exchange") or "").upper().replace(" ", "")
    if exchange not in _ALLOWED_EXCHANGES.get(market_type, set()):
        return "対象外市場またはOTC"
    if str(candidate.get("security_type") or "").lower() not in {
        "common_stock",
        "common stock",
        "ordinary_share",
    }:
        return "ETF・投資信託等"
    if str(candidate.get("theme") or "") not in allowed_themes:
        return "対象外テーマ"
    evidence_date = _parse_date(str(candidate.get("evidence_date") or ""))
    if evidence_date is None or evidence_date < cutoff:
        return "根拠が18か月超または日付不明"
    urls = _cited_source_urls(candidate, citation_lookup)
    if len(urls) < 2:
        return "検索引用または独立根拠不足"
    if not any(_is_primary_source(url, candidate) for url in urls):
        return "一次資料不足"
    return ""


def _cited_source_urls(
    candidate: dict[str, Any], citation_lookup: dict[str, dict[str, Any]]
) -> list[str]:
    raw_sources = candidate.get("sources", [])
    values = []
    for raw in raw_sources if isinstance(raw_sources, list) else []:
        url = raw.get("url") if isinstance(raw, dict) else raw
        canonical = _canonical_url(str(url or ""))
        if canonical and canonical in citation_lookup:
            values.append(canonical)
    return list(dict.fromkeys(values))


def _is_primary_source(url: str, candidate: dict[str, Any]) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":", 1)[0]
    path = parsed.path.lower()
    official = str(candidate.get("official_domain") or "").lower().strip()
    if official.startswith(("http://", "https://")):
        official = urlparse(official).netloc.lower()
    official = official.split(":", 1)[0].removeprefix("www.")
    company_host = host.removeprefix("www.")
    official_match = bool(official) and (
        company_host == official or company_host.endswith(f".{official}")
    )
    return host in _PRIMARY_DOMAINS or (
        official_match
        and any(token in path for token in ("/investor", "/investors", "/ir/", "/ir-"))
    )


def _round_robin_external(
    candidates: list[ValidatedExternalTicker], themes: list[str]
) -> list[ValidatedExternalTicker]:
    by_theme: dict[str, list[ValidatedExternalTicker]] = defaultdict(list)
    for item in candidates:
        primary = item.get("themes", [""])[0]
        by_theme[primary].append(item)
    for values in by_theme.values():
        values.sort(
            key=lambda item: (-int(item.get("evidence_quality") or 0), item["ticker"])
        )
    result: list[ValidatedExternalTicker] = []
    seen: set[str] = set()
    while len(result) < MAX_EXTERNAL_TICKERS:
        added = False
        for theme in themes:
            while by_theme[theme] and by_theme[theme][0]["ticker"] in seen:
                by_theme[theme].pop(0)
            if not by_theme[theme]:
                continue
            item = by_theme[theme].pop(0)
            result.append(item)
            seen.add(item["ticker"])
            added = True
            if len(result) >= MAX_EXTERNAL_TICKERS:
                break
        if not added:
            break
    return result


def _normalize_ticker(value: str, market_type: str) -> str:
    ticker = value.strip().upper().replace(" ", "")
    if market_type == "JP":
        code = ticker[:-2] if ticker.endswith(".T") else ticker
        return f"{code}.T" if code.isdigit() and len(code) == 4 else ""
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
    return ticker if ticker and len(ticker) <= 12 and set(ticker) <= allowed else ""


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _canonical_url(value: str) -> str:
    url = value.strip()
    if not url.startswith(("https://", "http://")):
        return ""
    parsed = urlparse(url)
    if not parsed.netloc:
        return ""
    return parsed._replace(fragment="").geturl().rstrip("/")


def _cache_key(market: str, values: list[str], model: str, version: str) -> str:
    raw = json.dumps([market, sorted(values), model, version], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _discovery_prompt(market: str, themes: list[str]) -> str:
    market_label = "米国上場" if market == "US" else "東京証券取引所上場"
    return (
        f"{market_label}の普通株から、次のテーマに事業売上・受注・設備投資で直接関係する"
        f"登録外候補を調査してください: {', '.join(themes)}。各テーマ最大{MAX_PER_THEME}件。"
        "大型代表銘柄だけでなく上場中小型株も探索してください。"
        "各候補には直近18か月以内の会社IR/SEC/EDINET/JPX等の一次資料と、"
        "別の独立根拠を付けてください。ETF、投資信託、OTC、上場廃止株は除外。"
        "銘柄の優劣・スコア・売買判断は生成しないでください。URLは検索で確認したものだけを記載。"
    )


def _discovery_schema(themes: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "maxItems": max(len(themes), 1) * MAX_PER_THEME,
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "exchange": {"type": "string"},
                        "company_name": {"type": "string"},
                        "theme": {"type": "string", "enum": themes},
                        "business_relationship": {"type": "string"},
                        "evidence_date": {"type": "string"},
                        "official_domain": {"type": "string"},
                        "security_type": {"type": "string"},
                        "sources": {
                            "type": "array",
                            "minItems": 2,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "url": {"type": "string"},
                                    "title": {"type": "string"},
                                    "source_type": {"type": "string"},
                                },
                                "required": ["url", "title", "source_type"],
                            },
                        },
                    },
                    "required": [
                        "ticker",
                        "exchange",
                        "company_name",
                        "theme",
                        "business_relationship",
                        "evidence_date",
                        "security_type",
                        "sources",
                    ],
                },
            }
        },
        "required": ["candidates"],
    }


def _deep_dive_prompt(market: str, candidates: list[dict[str, str]]) -> str:
    return (
        f"{market}市場の次の機械抽出済み研究候補を、直近の一次資料を優先して調査してください: "
        f"{json.dumps(candidates, ensure_ascii=False)}。各銘柄についてテーマとの事業関係、"
        "業績加速の有無、最新材料、反証、次回確認事項、検索で確認した出典URLを整理してください。"
        "順位、スコア、売買推奨は生成・変更しないでください。"
    )


def _deep_dive_schema() -> dict[str, Any]:
    fields = {
        key: {"type": "string"}
        for key in (
            "ticker",
            "business_relationship",
            "earnings_acceleration",
            "latest_catalyst",
            "counter_evidence",
            "next_check",
        )
    }
    fields["source_urls"] = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": fields,
                    "required": list(fields),
                },
            }
        },
        "required": ["items"],
    }
