import pandas as pd

from src.services.stock_analysis_inputs import StockAnalysisInputs


def test_stock_analysis_inputs_memoizes_each_request():
    calls: list[tuple[str, str]] = []

    def history(ticker: str, period: str) -> pd.DataFrame:
        calls.append((ticker, period))
        return pd.DataFrame({"Close": [1.0]})

    inputs = StockAnalysisInputs("aapl", history_provider=history)

    first = inputs.history("AAPL", "1y")
    second = inputs.history("aapl", "1y")

    assert first is second
    assert calls == [("AAPL", "1y")]
    assert inputs.benchmark == "SPY"


def test_stock_analysis_inputs_uses_japan_benchmark():
    inputs = StockAnalysisInputs("7203.t")

    assert inputs.ticker == "7203.T"
    assert inputs.benchmark == "1306.T"


def test_full_info_satisfies_later_summary_free_request():
    calls = []

    def info(ticker: str, **kwargs):
        calls.append((ticker, kwargs))
        return {"ticker": ticker, "summary": "Full"}

    inputs = StockAnalysisInputs("AAPL", info_provider=info)

    inputs.info("AAPL")
    inputs.info("AAPL", include_summary=False)

    assert len(calls) == 1


def test_long_history_satisfies_shorter_period_without_refetch():
    calls = []
    frame = pd.DataFrame({"Close": range(300)})

    def history(ticker: str, period: str):
        calls.append((ticker, period))
        return frame

    inputs = StockAnalysisInputs("AAPL", history_provider=history)

    inputs.history("AAPL", "5y")
    shorter = inputs.history("AAPL", "6mo")

    assert calls == [("AAPL", "5y")]
    assert len(shorter) == 126
