import numpy as np
import pandas as pd
import pytest

from src.services.volume_profile_service import build_volume_profile


def _history(rows: int = 126) -> pd.DataFrame:
    close = np.linspace(90, 110, rows)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": np.linspace(1_000_000, 2_000_000, rows),
        }
    )


def test_volume_profile_builds_24_bins_and_conserves_volume():
    frame = _history()
    result = build_volume_profile(frame)

    assert result["status"] == "available"
    assert len(result["bins"]) == 24
    assert result["poc"]["low"] < result["poc"]["high"]
    assert result["value_area"]["val"] < result["value_area"]["vah"]
    distributed = sum(item["volume"] for item in result["bins"])
    assert distributed == pytest.approx(frame["Volume"].sum(), rel=1e-8)


def test_volume_profile_requires_60_sessions():
    result = build_volume_profile(_history(59))

    assert result["status"] == "unavailable"
    assert "60営業日" in result["reason"]
