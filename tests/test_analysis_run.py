from src.services.analysis_context import DataResult
from src.services.analysis_run import AnalysisRun


def _run() -> AnalysisRun:
    return AnalysisRun(
        run_id="run-1",
        kind="stock",
        subject="AAPL",
        created_at="2026-05-27T00:00:00+00:00",
        inputs={"ticker": "AAPL", "period": "1y"},
        data_status=[
            DataResult(
                name="stock_profile",
                source="market_data",
                fetched_at="2026-05-27T00:00:00+00:00",
                cache_status="live",
            )
        ],
        generated_signal={"label": "Bullish", "confidence": 0.62},
        prompt_summary="Stock prompt summary",
        ai_output="AI report",
        warnings=["profile summary unavailable"],
        metadata={"model": "gemini"},
    )


def test_analysis_run_exports_stable_markdown_and_notebook_json():
    markdown = _run().to_markdown()

    assert markdown == _run().to_markdown()
    assert "# Analysis Run: stock / AAPL" in markdown
    assert "stock_profile: ok; source=market_data; cache=live" in markdown
    assert "AI report" in markdown

    notebook = _run().to_notebook_json()
    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["analysis_run"]["run_id"] == "run-1"
    assert notebook["cells"][0]["cell_type"] == "markdown"


def test_analysis_run_round_trips_from_mapping():
    payload = _run().to_dict()

    restored = AnalysisRun.from_mapping(payload)

    assert restored.to_dict() == payload
