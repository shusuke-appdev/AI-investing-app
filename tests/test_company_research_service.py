from src.services import company_research_service as service


def test_calculate_dcf_returns_auditable_per_share_value():
    value = service.calculate_dcf(
        starting_fcf=100.0,
        growth_rate=0.05,
        wacc=0.10,
        terminal_growth=0.02,
        net_debt=50.0,
        shares=10.0,
    )

    assert value is not None
    assert round(value, 2) == 139.62


def test_calculate_dcf_rejects_invalid_economics():
    assert (
        service.calculate_dcf(
            starting_fcf=100.0,
            growth_rate=0.05,
            wacc=0.02,
            terminal_growth=0.02,
            net_debt=0.0,
            shares=10.0,
        )
        is None
    )


def test_calculate_sotp_uses_only_supported_segment_inputs():
    result = service.calculate_sotp(
        [
            {"name": "Cloud", "metric": 100.0, "multiple": 8.0},
            {"name": "Other", "metric": None, "multiple": 2.0},
        ],
        net_debt=100.0,
        shares=10.0,
    )

    assert result["status"] == "available"
    assert result["per_share"] == 70.0
    assert [item["name"] for item in result["segments"]] == ["Cloud"]


def test_general_valuation_builds_three_cases_and_discount_label():
    result = service.build_equity_valuation(
        {
            "current_price": 100.0,
            "currency": "USD",
            "share_outstanding": 10.0,
            "freeCashflow": 150.0,
            "totalCash": 20.0,
            "totalDebt": 50.0,
            "revenueGrowth": 5.0,
        }
    )

    assert result["status"] == "available"
    assert result["method"] == "簡易FCF DCF"
    assert result["current_price_display"] == "USD 100.00"
    assert [item["key"] for item in result["cases"]] == ["bear", "base", "bull"]
    assert result["discount_label"] in {"割安候補", "適正圏", "割高候補"}


def test_missing_cash_flow_remains_explicitly_unavailable():
    result = service.build_equity_valuation(
        {"current_price": 100.0, "share_outstanding": 10.0}
    )

    assert result["status"] == "unavailable"
    assert result["base_value"] is None
    assert result["discount_label"] == "判定不能"


def test_financial_profile_treats_sub_one_percent_roe_as_percentage_points():
    result = service.build_equity_valuation(
        {
            "current_price": 100.0,
            "share_outstanding": 10.0,
            "bookValue": 80.0,
            "returnOnEquity": 0.5,
        },
        profile="bank",
    )

    base = next(item for item in result["cases"] if item["key"] == "base")
    assert base["assumptions"]["roe"] == 0.005


def test_grounded_research_keeps_only_cited_official_sources(monkeypatch):
    monkeypatch.setattr(
        service,
        "generate_grounded_structured",
        lambda prompt, schema: {
            "status": "available",
            "data": {
                "segments": [
                    {
                        "name": "Cloud",
                        "summary": "成長",
                        "source_url": "https://www.sec.gov/Archives/test",
                    },
                    {
                        "name": "Rumor",
                        "summary": "未検証",
                        "source_url": "https://example-news.invalid/story",
                    },
                ],
                "guidance": [],
                "catalysts": [],
                "risks": [],
                "outlook": "一次資料の範囲内で条件付き。",
                "outlook_source_url": "https://www.sec.gov/Archives/test",
            },
            "citations": [
                {"url": "https://www.sec.gov/Archives/test", "title": "10-K"},
                {"url": "https://example-news.invalid/story", "title": "News"},
            ],
            "model": "test-model",
            "warnings": [],
            "total_tokens": 100,
            "search_query_count": 1,
        },
    )

    result = service._grounded_filings_research(
        "TEST", {"name": "Test Inc.", "website": "https://test.example"}, "US"
    )

    assert result["status"] == "available"
    assert [item["name"] for item in result["segments"]] == ["Cloud"]
    assert result["sources"] == [
        {
            "url": "https://www.sec.gov/Archives/test",
            "title": "10-K",
            "source_type": "primary",
        }
    ]
