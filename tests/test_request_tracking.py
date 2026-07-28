import asyncio

import pytest

from frontend.state import theme_state as theme_state_module
from frontend.state.error_handling import user_facing_error
from frontend.state.market_state import MarketState
from frontend.state.request_tracking import is_current_request
from frontend.state.stock_state import StockState
from frontend.state.theme_state import ThemeState
from src.provider_result import FetchResult


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


def test_user_facing_error_does_not_expose_provider_details():
    error = user_facing_error(
        "市場データの取得",
        ConnectionError("https://provider.invalid/?token=secret-token"),
    )

    assert error.code == "connection_error"
    assert error.retryable is True
    assert "secret-token" not in error.message
    assert "provider.invalid" not in error.message


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


def test_theme_market_change_invalidates_rows_and_refreshes_only_theme_routes():
    state = ThemeState(_reflex_internal_init=True)
    state.ranked_themes = [
        {
            "theme": "US semiconductor",
            "performance": 2.0,
            "stocks": [],
        }
    ]
    state.loaded_market_type = "US"
    state.router.url.path = "/theme"

    event = state.set_market_type("JP")

    assert event == ThemeState.fetch_themes
    assert state.requested_market_type == "JP"
    assert state.loaded_market_type == ""
    assert state.ranked_themes == []
    assert state.theme_request_id == 1

    state.router.url.path = "/stock"
    assert state.set_market_type("US") is None
    assert state.requested_market_type == "US"
    assert state.theme_request_id == 2


def test_theme_period_change_invalidates_inflight_result(monkeypatch):
    state = ThemeState(_reflex_internal_init=True)
    market_state = MarketState(_reflex_internal_init=True)
    market_state.market_type = "US"

    async def fake_get_state(self, state_cls):
        assert state_cls is MarketState
        return market_state

    async def fake_to_thread(function, *args):
        assert args == ("1週間", "US")
        return FetchResult(
            data=[
                {
                    "theme": "Semiconductor",
                    "performance": 3.2,
                    "stocks": [],
                    "requested_days": 7,
                    "component_count": 2,
                    "total_components": 2,
                    "coverage": 1.0,
                }
            ],
            source="test",
            fetched_at="2026-07-28T00:00:00+00:00",
        )

    monkeypatch.setattr(ThemeState, "get_state", fake_get_state)
    monkeypatch.setattr(theme_state_module.asyncio, "to_thread", fake_to_thread)

    async def exercise():
        events = state.fetch_themes()
        await anext(events)
        state.set_period("1ヶ月")
        with pytest.raises(StopAsyncIteration):
            await anext(events)

    asyncio.run(exercise())

    assert state.selected_period == "1ヶ月"
    assert state.ranked_themes == []
    assert state.loaded_period == ""
    assert state.is_fetching is False


def test_theme_fetch_commits_matching_market_period_result(monkeypatch):
    state = ThemeState(_reflex_internal_init=True)
    market_state = MarketState(_reflex_internal_init=True)
    market_state.market_type = "JP"

    async def fake_get_state(self, state_cls):
        assert state_cls is MarketState
        return market_state

    async def fake_to_thread(function, *args):
        assert args == ("1週間", "JP")
        return FetchResult(
            data=[
                {
                    "theme": "半導体",
                    "performance": 1.5,
                    "stocks": [{"ticker": "7203.T", "performance": 1.0}],
                    "requested_days": 7,
                    "component_count": 2,
                    "total_components": 3,
                    "coverage": 2 / 3,
                }
            ],
            source="test",
            fetched_at="2026-07-28T00:00:00+00:00",
        )

    monkeypatch.setattr(ThemeState, "get_state", fake_get_state)
    monkeypatch.setattr(theme_state_module.asyncio, "to_thread", fake_to_thread)

    async def exercise():
        events = state.fetch_themes()
        await anext(events)
        await anext(events)
        with pytest.raises(StopAsyncIteration):
            await anext(events)

    asyncio.run(exercise())

    assert state.requested_market_type == "JP"
    assert state.loaded_market_type == "JP"
    assert state.loaded_period == "1週間"
    assert state.loaded_at == "2026-07-28T00:00:00+00:00"
    assert state.ranked_themes[0].theme == "半導体"
    assert state.is_fetching is False
