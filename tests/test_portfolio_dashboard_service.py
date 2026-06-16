from types import SimpleNamespace

from src.services.portfolio_dashboard_service import (
    holdings_to_payload,
    run_portfolio_analysis,
    validate_holding_input,
)


def test_validate_holding_input_requires_positive_shares():
    result = validate_holding_input("AAPL", "0", "")

    assert not result.is_valid
    assert "0より大きい" in result.error


def test_validate_holding_input_normalizes_valid_values():
    result = validate_holding_input(" aapl ", "2.5", "150")

    assert result.is_valid
    assert result.ticker == "AAPL"
    assert result.shares == 2.5
    assert result.avg_cost == 150.0


def test_holdings_to_payload_filters_non_positive_rows():
    payload = holdings_to_payload(
        [
            SimpleNamespace(ticker="AAPL", shares=2, avg_cost=150.0),
            SimpleNamespace(ticker="MSFT", shares=0, avg_cost=None),
        ]
    )

    assert payload == [{"ticker": "AAPL", "shares": 2.0, "avg_cost": 150.0}]


def test_portfolio_analysis_excludes_missing_prices(monkeypatch):
    from src.advisor import analysis

    monkeypatch.setattr(
        analysis,
        "get_stock_info",
        lambda ticker: {"current_price": 100.0 if ticker == "AAPL" else None},
    )
    monkeypatch.setattr(analysis, "analyze_technical", lambda ticker: None)

    result = run_portfolio_analysis(
        [
            {"ticker": "AAPL", "shares": 2, "avg_cost": 90},
            {"ticker": "MISSING", "shares": 3, "avg_cost": 10},
        ]
    )

    assert result["total_value"] == 200.0
    assert result["num_holdings"] == 1
    assert result["excluded_holdings"][0]["ticker"] == "MISSING"
    assert result["provenance"][0]["kind"] == "direct"


def test_portfolio_ai_accepts_serialized_technical_analysis(monkeypatch):
    from src.advisor import llm

    monkeypatch.setattr(llm, "get_macro_context", lambda: {})
    monkeypatch.setattr(llm, "analyze_market_technicals", lambda: {})
    monkeypatch.setattr(llm, "get_sector_performance", lambda: {})
    monkeypatch.setattr(llm, "get_theme_exposure_analysis", lambda holdings: {})
    monkeypatch.setattr(llm, "get_holdings_news", lambda holdings: [])
    monkeypatch.setattr(llm, "generate_content", lambda prompt: prompt)
    monkeypatch.setattr(
        "src.knowledge_storage.get_knowledge_for_ai_context", lambda max_items: ""
    )
    analysis = {
        "total_value": 200.0,
        "num_holdings": 1,
        "holdings": [
            {
                "ticker": "AAPL",
                "name": "Apple",
                "current_price": 100.0,
                "shares": 2.0,
                "value": 200.0,
                "weight": 100.0,
                "pnl_pct": 10.0,
                "technical": {
                    "overall_signal": "Buy",
                    "overall_score": 3,
                    "rsi": 55.0,
                    "rsi_signal": "Neutral",
                    "macd_signal": "Bullish",
                    "contrarian_signal": "Wait",
                    "contrarian_buy_zone": [90.0, 95.0],
                    "support_price": 88.0,
                },
            }
        ],
    }

    prompt = llm.generate_portfolio_advice(
        analysis, include_macro=False, include_news=False
    )

    assert "テクニカル: Buy" in prompt
    assert "売買数量や注文を指示しない" in prompt
    assert "未信頼の引用データ" in prompt


def test_portfolio_ai_reuses_market_context_without_market_refetch(monkeypatch):
    from src.advisor import llm
    from src.services.analysis_context import DataResult, MarketContext, ProvenanceItem

    def fail_fetch():
        raise AssertionError("market fetch should not run when context is supplied")

    monkeypatch.setattr(llm, "get_macro_context", fail_fetch)
    monkeypatch.setattr(llm, "analyze_market_technicals", fail_fetch)
    monkeypatch.setattr(llm, "get_sector_performance", fail_fetch)
    monkeypatch.setattr(llm, "get_holdings_news", lambda holdings: [])
    monkeypatch.setattr(llm, "generate_content", lambda prompt: prompt)
    monkeypatch.setattr(
        "src.knowledge_storage.get_knowledge_for_ai_context", lambda max_items: ""
    )
    analysis = {
        "total_value": 200.0,
        "num_holdings": 1,
        "holdings": [
            {
                "ticker": "AAPL",
                "name": "Apple",
                "current_price": 100.0,
                "shares": 2.0,
                "value": 200.0,
                "weight": 100.0,
                "technical": None,
            }
        ],
    }
    market_context = MarketContext(
        market_type="US",
        evaluation={"status": "Neutral", "score": 0.0, "signals": []},
        data_status=[
            DataResult(
                name="market_indices",
                source="persistent_cache",
                is_stale=True,
                cache_status="stale_cache",
                error="using stale fallback",
            )
        ],
        provenance=[
            ProvenanceItem(
                item_id="market.indices",
                label="Market indices",
                source="persistent_cache",
                limitation="stale fallback",
            )
        ],
    )

    prompt = llm.generate_portfolio_advice(
        analysis,
        market_context=market_context,
        include_news=False,
    )

    assert "共有MarketContext" in prompt
    assert "persistent_cache" in prompt
    assert "stale fallback" in prompt
