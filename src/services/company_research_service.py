"""On-demand, source-labelled company research and deterministic valuation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from src.gemini_client import generate_grounded_structured
from src.persistent_cache import repo_state_cache
from src.services.equity_valuation_service import _profile_key
from src.services.equity_valuation_service import (
    build_equity_valuation as build_equity_valuation,
)
from src.services.equity_valuation_service import calculate_dcf as calculate_dcf
from src.services.equity_valuation_service import calculate_sotp as calculate_sotp

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


def _canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return parsed._replace(fragment="").geturl()
