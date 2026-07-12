import pandas as pd

from src.economic_data_provider import EconomicDataResult
from src.marketdata_option_provider import MarketDataOptionResult
from src.provider_result import FetchResult
from src.stock_data_provider import HistoryResult, QuoteResult


def test_provider_results_share_fetch_contract():
    results = (
        QuoteResult(data={"price": 100.0}),
        HistoryResult(data=pd.DataFrame({"Close": [100.0]})),
        EconomicDataResult(data=pd.DataFrame({"GDP": [1.0]})),
        MarketDataOptionResult(
            calls=pd.DataFrame({"strike": [100.0]}),
            puts=pd.DataFrame({"strike": [100.0]}),
        ),
    )

    assert all(isinstance(result, FetchResult) for result in results)
    assert all(hasattr(result, "cache_status") for result in results)
    assert all(hasattr(result, "warnings") for result in results)


def test_fetch_result_distinguishes_empty_payload_from_zero_value():
    assert FetchResult(data={"price": 0.0}).is_available is True
    assert FetchResult(data={}).is_available is False
    assert FetchResult(data=pd.DataFrame()).is_available is False


def test_marketdata_compatibility_warning_alias_updates_shared_warnings():
    result = MarketDataOptionResult(
        calls=pd.DataFrame(),
        puts=pd.DataFrame(),
        quality_warnings=["stale chain"],
    )

    assert result.warnings == ["stale chain"]
    assert result.metadata()["quality_warnings"] == ["stale chain"]
