import pandas as pd

from src import sector_flow_monitor as monitor


def test_sector_flow_monitor_ranks_flow_pressure_leader(monkeypatch):
    dates = pd.date_range("2025-01-01", periods=140, freq="B")
    close_paths = {
        ticker: _linear(100.0, 102.0, len(dates)) for ticker in monitor.FLOW_UNIVERSE
    }
    close_paths["SPY"] = _linear(100.0, 105.0, len(dates))
    close_paths["SMH"] = [100.0] * 100 + _linear(100.0, 155.0, 40)
    close_paths["KRE"] = _linear(100.0, 80.0, len(dates))
    frame = pd.DataFrame(
        {(ticker, "Close"): close_paths[ticker] for ticker in monitor.FLOW_UNIVERSE}
        | {
            (ticker, "Volume"): [1_000_000 + i * 1000 for i in range(len(dates))]
            for ticker in monitor.FLOW_UNIVERSE
        },
        index=dates,
    )
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    monkeypatch.setattr(monitor, "_download_universe", lambda: frame)

    result = monitor.build_sector_flow_monitor("US")

    assert result["status"] in {"risk_on", "risk_off"}
    assert result["leaders"][0]["ticker"] == "SMH"
    assert any(item["ticker"] == "KRE" for item in result["laggards"])


def _linear(start: float, end: float, length: int) -> list[float]:
    step = (end - start) / (length - 1)
    return [start + step * index for index in range(length)]
