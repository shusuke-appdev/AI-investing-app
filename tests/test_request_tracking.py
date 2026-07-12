from frontend.state.market_state import MarketState
from frontend.state.request_tracking import is_current_request
from frontend.state.stock_state import StockState


def test_current_request_requires_matching_id_and_key():
    assert is_current_request(
        current_id=2,
        current_key="AAPL",
        request_id=2,
        request_key="AAPL",
    )
    assert not is_current_request(
        current_id=3,
        current_key="AAPL",
        request_id=2,
        request_key="AAPL",
    )


def test_stock_ticker_change_invalidates_inflight_requests():
    state = StockState(_reflex_internal_init=True)
    state.ticker = "AAPL"
    state.fetch_request_id = 4
    state.analysis_request_id = 2

    state.set_ticker("MSFT")

    assert state.fetch_request_id == 5
    assert state.analysis_request_id == 3
    assert not state._is_current_fetch(4, "AAPL")


def test_market_change_invalidates_data_and_recap_requests():
    state = MarketState(_reflex_internal_init=True)
    state.market_type = "US"
    state.market_request_id = 7
    state.recap_request_id = 3

    event = state.set_market_type("JP")

    assert event == MarketState.fetch_market_summary_fast
    assert state.market_request_id == 8
    assert state.recap_request_id == 4
    assert not state._is_current_market_request(7, "US")
    assert not is_current_request(
        current_id=2,
        current_key="MSFT",
        request_id=2,
        request_key="AAPL",
    )
