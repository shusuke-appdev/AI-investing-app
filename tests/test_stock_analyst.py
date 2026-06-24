from src import stock_analyst
from src.stock_analyst import (
    _format_provenance_context,
    _format_sector_theme_context,
    _format_trade_setup_context,
    _format_trend_follow_context,
)


def test_format_trend_follow_context_marks_diagnostics_as_context_only():
    context = {
        "trend_follow_diagnostics": {
            "rating_display": "Fragile",
            "current_state_display": "50D MA is above 200D MA.",
            "strategy_total_return_display": "+12.30%",
            "buy_hold_total_return_display": "+20.00%",
            "oos_alpha_display": "-4.20%",
            "top5_removed_display": "-1.00%",
            "random_percentile_display": "42.00%",
            "strategy_max_drawdown_display": "-18.00%",
            "strategy_tuw_display": "140 days",
            "warnings": ["OOS return did not beat Buy & Hold."],
        }
    }

    text = _format_trend_follow_context(context)

    assert "diagnostic only" in text
    assert "Fragile" in text
    assert "OOS return did not beat Buy & Hold." in text


def test_format_trend_follow_context_handles_missing_data():
    assert _format_trend_follow_context({}) == "Trend-Follow Diagnostics: unavailable."


def test_format_trade_setup_context_preserves_blocked_status():
    text = _format_trade_setup_context(
        {
            "trade_setup": {
                "status": "blocked",
                "grade": "A",
                "score_display": "90/100",
                "blocked_reasons": ["下降する200MAに逆らうEntryは禁止。"],
                "warnings": ["LoDは未判定。"],
            }
        }
    )

    assert "Status: blocked" in text
    assert "Do not override" in text


def test_analyze_stock_reuses_supplied_context_without_recomputing(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        stock_analyst,
        "get_technical_summary_for_ai",
        lambda ticker: (_ for _ in ()).throw(AssertionError("should not recompute")),
    )

    def fake_generate_content(prompt):
        captured["prompt"] = prompt
        return "ok"

    monkeypatch.setattr(stock_analyst, "generate_content", fake_generate_content)

    from src.advisor import smart_criteria

    monkeypatch.setattr(
        smart_criteria,
        "evaluate_smart_criteria",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not recompute SMART")
        ),
    )
    monkeypatch.setattr(
        "src.knowledge_storage.get_knowledge_for_ai_context",
        lambda max_items=5: "",
    )

    result = stock_analyst.analyze_stock(
        "TEST",
        {
            "name": "Test Co",
            "sector": "Technology",
            "industry": "Software",
            "market_cap": 1_000_000_000,
            "current_price": 100,
        },
        stock_signal_context={
            "technical_data": {
                "overall_signal": "Buy",
                "overall_score": 72,
                "rsi": 55,
            },
            "smart_criteria": {
                "S": {"met": True, "desc": "Sales", "value": "30%"},
                "M": {"met": False, "desc": "Margin", "value": "N/A"},
            },
            "probabilistic_signal": {"signal_label": "Constructive"},
            "news_headlines": ["Context headline"],
            "provenance": [
                {
                    "item_id": "technical_score",
                    "label": "Technical score",
                    "kind": "model_output",
                    "source": "local indicators",
                    "method": "weighted score",
                    "limitation": "Not a direct quote",
                    "risk_level": "medium",
                }
            ],
        },
    )

    assert result == "ok"
    assert "総合シグナル: Buy" in captured["prompt"]
    assert "S: ✅ Sales" in captured["prompt"]
    assert "Context headline" in captured["prompt"]
    assert "Constructive" in captured["prompt"]
    assert "Data provenance:" in captured["prompt"]
    assert "kind=model_output" in captured["prompt"]


def test_format_sector_theme_context_includes_advantage_flags():
    text = _format_sector_theme_context(
        {
            "sector_theme_context": {
                "sector": "Technology",
                "themes": ["AI"],
                "fundamental_advantage": True,
                "flow_advantage": True,
                "combined_rating": "high",
                "rationale": "Both advantages exist.",
                "theme_diagnostics": [
                    {
                        "theme": "AI",
                        "fundamental_score": 0.75,
                        "flow_score": 0.7,
                        "classification": "fundamental_and_flow_aligned",
                    }
                ],
            }
        }
    )

    assert "Sector/Theme Context" in text
    assert "Combined Rating: high" in text
    assert "fundamental=True" in text or "Stock Fundamental Advantage: True" in text


def test_format_provenance_context_handles_missing_data():
    assert _format_provenance_context({}) == ""


def test_analyze_stock_keeps_missing_core_metrics_unavailable(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        stock_analyst,
        "generate_content",
        lambda prompt: captured.setdefault("prompt", prompt) and "ok",
    )
    monkeypatch.setattr(
        "src.knowledge_storage.get_knowledge_for_ai_context",
        lambda max_items=5: "",
    )

    result = stock_analyst.analyze_stock(
        "TEST",
        {"name": "Test Co", "sector": "Technology", "industry": "Software"},
        stock_signal_context={
            "technical_data": {"overall_signal": "Hold"},
            "smart_criteria": {"S": {"status": "unknown", "value": "N/A"}},
        },
    )

    assert result == "ok"
    assert "時価総額: N/A" in captured["prompt"]
    assert "現在株価: N/A" in captured["prompt"]
    assert "アナリスト目標株価: N/A" in captured["prompt"]
    assert "$0.00" not in captured["prompt"]
