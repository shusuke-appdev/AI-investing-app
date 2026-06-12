import numpy as np
import pandas as pd

from src.advisor.fomo_volatility_regime import (
    analyze_fomo_volatility_regime,
    scan_fomo_universe,
)


def _prices(rows: int = 140) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="B")
    close = np.linspace(100, 150, rows)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(rows, 1_000_000.0),
        },
        index=index,
    )


def test_fomo_regime_reports_trend_state_and_profile():
    result = analyze_fomo_volatility_regime(_prices(), ticker="TEST")

    assert result["ticker"] == "TEST"
    assert result["state"] in {
        "trend_continuation",
        "breakout",
        "pullback_candidate",
        "neutral",
    }
    assert result["profile"]["name"] == "established"
    assert result["data_quality"]["status"] == "ok"


def test_fomo_regime_flags_overheated_fomo_day():
    frame = _prices()
    frame.loc[frame.index[-1], ["Open", "High", "Low", "Close", "Volume"]] = [
        149,
        170,
        148,
        169,
        4_000_000,
    ]

    result = analyze_fomo_volatility_regime(frame, ticker="TEST")

    assert result["state"] in {"fomo_momentum", "fomo_buying", "volatility_overheat"}
    assert result["risk_level"] == "elevated"


def test_fomo_regime_requires_minimum_history():
    result = analyze_fomo_volatility_regime(_prices(40), ticker="NEW")

    assert result["state"] == "insufficient_data"


def test_fomo_regime_marks_synthesized_ohlcv_as_proxy():
    result = analyze_fomo_volatility_regime(_prices()[["Close"]], ticker="PROXY")

    assert result["data_quality"]["status"] == "proxy"
    assert result["data_quality"]["synthesized_fields"] == [
        "open",
        "high",
        "low",
        "volume",
    ]


def test_fomo_scan_preserves_partial_success():
    def fetcher(ticker: str, period: str) -> pd.DataFrame:
        if ticker == "FAIL":
            raise RuntimeError("provider unavailable")
        return _prices()

    result = scan_fomo_universe(fetcher, ["OK", "FAIL"], max_workers=2)

    assert result["summary"] == "1/2銘柄を判定"
    assert result["is_partial"] is True
    assert result["items"][0]["ticker"] == "OK"
