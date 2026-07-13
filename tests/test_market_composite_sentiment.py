import numpy as np
import pandas as pd

from src.market_volatility_intelligence import CboeIndexResult
from src.services.market_composite_sentiment import compute_market_composite_sentiment
from src.services.occ_put_call_service import OccPutCallResult


def _prices(index: pd.DatetimeIndex, weak_breadth: bool = False):
    spy = np.linspace(100, 120, len(index))
    rsp = np.linspace(100, 118 if weak_breadth else 122, len(index))
    iwm = np.linspace(100, 117 if weak_breadth else 121, len(index))
    qqq = np.linspace(100, 125, len(index))
    return {
        "SPY": pd.DataFrame({"Close": spy}, index=index),
        "QQQ": pd.DataFrame({"Close": qqq}, index=index),
        "RSP": pd.DataFrame({"Close": rsp}, index=index),
        "IWM": pd.DataFrame({"Close": iwm}, index=index),
    }


def _occ(index: pd.DatetimeIndex, last_ratio: float = 1.0):
    values = np.linspace(0.7, 1.2, len(index))
    values[-1] = last_ratio
    history = pd.DataFrame({"put_call_ratio": values}, index=index)
    return OccPutCallResult(
        symbol="SPY",
        history=history,
        status="available",
        as_of=str(index[-1].date()),
    )


def test_hidden_tail_hedging_combines_falling_vix_and_high_skew():
    index = pd.date_range("2025-01-02", periods=100, freq="B")
    vix = np.concatenate([np.linspace(30, 20, 94), np.linspace(20, 15, 6)])
    cboe = pd.DataFrame(
        {
            "VIX": vix,
            "VIX9D": vix * 0.95,
            "VIX3M": vix * 1.2,
            "VVIX": np.linspace(110, 90, len(index)),
            "SKEW": [125.0] * 99 + [155.0],
        },
        index=index,
    )

    result = compute_market_composite_sentiment(
        _prices(index),
        CboeIndexResult(data=cboe, source="test"),
        [],
        {"SPY": _occ(index), "QQQ": _occ(index)},
    )

    assert result["targets"]["SPY"]["state"] == "hidden_tail_hedging"
    assert result["targets"]["SPY"]["risk_floor"] == "medium"


def test_vix_vvix_and_negative_gamma_confirm_downside_amplification():
    index = pd.date_range("2025-01-02", periods=100, freq="B")
    vix = np.concatenate([np.linspace(15, 16, 94), np.linspace(16, 22, 6)])
    vvix = np.concatenate([np.linspace(85, 90, 94), np.linspace(90, 125, 6)])
    cboe = pd.DataFrame(
        {
            "VIX": vix,
            "VIX9D": vix * 1.08,
            "VIX3M": vix * 0.95,
            "VVIX": vvix,
            "SKEW": np.linspace(125, 135, len(index)),
        },
        index=index,
    )
    option = {
        "ticker": "SPY",
        "provider_active": True,
        "complete_status": "complete",
        "gamma_coverage": 1.0,
        "gex": {"nearby_net_gex": -5000.0},
        "source": "test Greeks",
    }

    result = compute_market_composite_sentiment(
        _prices(index, weak_breadth=True),
        CboeIndexResult(data=cboe, source="test"),
        [option],
        {"SPY": _occ(index), "QQQ": _occ(index)},
    )

    spy = result["targets"]["SPY"]
    assert spy["state"] == "downside_amplification"
    assert spy["status"] == "confirmed"
    assert spy["risk_floor"] in {"high", "extreme"}


def test_missing_gamma_keeps_amplification_partial_and_non_binding():
    index = pd.date_range("2025-01-02", periods=100, freq="B")
    vix = np.concatenate([np.linspace(15, 16, 94), np.linspace(16, 22, 6)])
    vvix = np.concatenate([np.linspace(85, 90, 94), np.linspace(90, 125, 6)])
    cboe = pd.DataFrame(
        {
            "VIX": vix,
            "VIX9D": vix,
            "VIX3M": vix * 1.1,
            "VVIX": vvix,
            "SKEW": np.linspace(125, 135, len(index)),
        },
        index=index,
    )

    result = compute_market_composite_sentiment(
        _prices(index),
        CboeIndexResult(data=cboe, source="test"),
        [],
        {"SPY": _occ(index), "QQQ": _occ(index)},
    )

    spy = result["targets"]["SPY"]
    assert spy["state"] == "downside_amplification"
    assert spy["status"] == "partial"
    assert spy["risk_floor"] == "none"
