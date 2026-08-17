from __future__ import annotations

from datetime import date

from src.services import theme_grounded_research_service as service


def _generated(candidates, urls):
    return {
        "status": "available",
        "data": {"candidates": candidates},
        "citations": [
            {"url": url, "title": f"source-{index}"} for index, url in enumerate(urls)
        ],
        "model": "gemini-test",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "search_query_count": 2,
        "warnings": [],
        "error": "",
    }


def _candidate(**overrides):
    value = {
        "ticker": "SMCI",
        "exchange": "NASDAQ",
        "company_name": "Super Micro Computer",
        "theme": "AIサーバー",
        "business_relationship": "AIサーバーを販売",
        "evidence_date": "2026-06-01",
        "security_type": "common_stock",
        "sources": [
            {"url": "https://www.sec.gov/Archives/example", "title": "10-K"},
            {"url": "https://example.com/report", "title": "industry"},
        ],
    }
    value.update(overrides)
    return value


def test_grounded_external_candidate_requires_cited_primary_and_second_source():
    context = service.validate_external_discovery(
        market_type="US",
        themes=["AIサーバー"],
        generated=_generated(
            [_candidate()],
            ["https://www.sec.gov/Archives/example", "https://example.com/report"],
        ),
        fetched_at="2026-08-17T00:00:00+00:00",
        today=date(2026, 8, 17),
    )

    assert [item["ticker"] for item in context["validated"]] == ["SMCI"]
    assert context["validated"][0]["validation_status"] == "source_verified"
    assert context["search_query_count"] == 2


def test_uncited_url_old_evidence_and_etf_are_unverified_not_scored():
    uncited = _candidate()
    old = _candidate(ticker="OLD", evidence_date="2024-01-01")
    etf = _candidate(ticker="QQQ", security_type="ETF")
    context = service.validate_external_discovery(
        market_type="US",
        themes=["AIサーバー"],
        generated=_generated(
            [uncited, old, etf],
            ["https://www.sec.gov/Archives/example"],
        ),
        fetched_at="2026-08-17T00:00:00+00:00",
        today=date(2026, 8, 17),
    )

    assert context["validated"] == []
    assert len(context["unverified"]) == 3
    assert context["excluded_reasons"]["検索引用または独立根拠不足"] == 1
    assert context["excluded_reasons"]["根拠が18か月超または日付不明"] == 1
    assert context["excluded_reasons"]["ETF・投資信託等"] == 1


def test_jp_ticker_normalization_and_duplicate_theme_membership():
    first = _candidate(
        ticker="6526",
        exchange="TSE",
        company_name="ソシオネクスト",
        theme="AI半導体",
    )
    second = _candidate(
        ticker="6526.T",
        exchange="JPX",
        company_name="ソシオネクスト",
        theme="エッジAI",
    )
    context = service.validate_external_discovery(
        market_type="JP",
        themes=["AI半導体", "エッジAI"],
        generated=_generated(
            [first, second],
            ["https://www.sec.gov/Archives/example", "https://example.com/report"],
        ),
        fetched_at="2026-08-17T00:00:00+00:00",
        today=date(2026, 8, 17),
    )

    assert len(context["validated"]) == 1
    assert context["validated"][0]["ticker"] == "6526.T"
    assert set(context["validated"][0]["themes"]) == {"AI半導体", "エッジAI"}
