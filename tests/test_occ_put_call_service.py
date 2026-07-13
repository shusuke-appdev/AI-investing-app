from datetime import date
from types import SimpleNamespace

from src.services.occ_put_call_service import (
    _parse_occ_volume_csv,
    fetch_occ_put_call_day,
)


def test_parse_occ_volume_csv_aggregates_calls_and_puts():
    text = "\n".join(
        [
            "quantity,underlying,symbol,actype,porc,exchange,actdate,contractDate",
            "100,SPY,SPY,C,C,CBOE,07/09/2026,07/09/2026",
            "50,SPY,SPY,M,C,AMEX,07/09/2026,07/09/2026",
            "225,SPY,SPY,C,P,CBOE,07/09/2026,07/09/2026",
        ]
    )

    result = _parse_occ_volume_csv(text, "SPY", date(2026, 7, 9))

    assert result is not None
    assert result["calls"] == 150
    assert result["puts"] == 225
    assert result["put_call_ratio"] == 1.5


def test_fetch_occ_put_call_day_uses_requested_symbol_and_date():
    response = SimpleNamespace(
        text="quantity,porc\n10,C\n20,P\n",
        raise_for_status=lambda: None,
    )

    class Session:
        def get(self, url, **kwargs):
            assert kwargs["params"]["symbol"] == "QQQ"
            assert kwargs["params"]["reportDate"] == "20260709"
            return response

    result = fetch_occ_put_call_day("qqq", date(2026, 7, 9), session=Session())

    assert result is not None
    assert result["put_call_ratio"] == 2.0
