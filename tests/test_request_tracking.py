import asyncio

import pytest

from frontend.state import market_state as market_state_module
from frontend.state import theme_state as theme_state_module
from frontend.state.error_handling import user_facing_error
from frontend.state.market_state import MarketState
from frontend.state.request_tracking import is_current_request
from frontend.state.stock_state import StockState
from frontend.state.theme_state import ThemeItem, ThemeState, ThemeStock
from src.provider_result import FetchResult
from src.services.analysis_context import MarketContext


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

    state.router.url.path = "/market-watch"
    assert state.set_market_type("JP") is None


def test_prepare_market_watch_applies_cached_details_before_live_refresh(monkeypatch):
    state = MarketState(_reflex_internal_init=True)
    applied: list[str] = []

    def fake_apply(self, context):
        applied.append(context.source)
        self.market_context = context.to_dict()
        self.indices_data = [{"name": context.source}]

    async def fake_to_thread(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(MarketState, "_apply_market_context", fake_apply)
    monkeypatch.setattr(market_state_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(
        market_state_module,
        "load_cached_market_full_context",
        lambda market: MarketContext(market_type=market, source="cached_full"),
    )
    monkeypatch.setattr(
        market_state_module,
        "build_market_summary_context",
        lambda market: MarketContext(market_type=market, source="live_summary"),
    )
    monkeypatch.setattr(
        market_state_module,
        "build_market_analysis_inputs",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        market_state_module,
        "build_market_theme_flow_context",
        lambda market, context, **kwargs: MarketContext(
            market_type=market, source="live_theme_flow"
        ),
    )

    async def exercise():
        events = state.prepare_market_watch()
        await anext(events)
        await anext(events)
        assert applied == ["cached_full"]
        while True:
            try:
                await anext(events)
            except StopAsyncIteration:
                break

    asyncio.run(exercise())
    assert applied == ["cached_full", "live_summary", "live_theme_flow"]


def test_detail_refresh_starts_credit_and_options_together_and_keeps_credit(
    monkeypatch,
):
    import threading

    state = MarketState(_reflex_internal_init=True)
    barrier = threading.Barrier(2)
    applied: list[str] = []

    def fake_apply(self, context):
        applied.append(context.source)
        self.market_context = context.to_dict()

    def credit(market, context):
        barrier.wait(timeout=2)
        return MarketContext(market_type=market, source="credit")

    def options(market):
        barrier.wait(timeout=2)
        raise TimeoutError("option timeout")

    monkeypatch.setattr(MarketState, "_apply_market_context", fake_apply)
    monkeypatch.setattr(
        market_state_module, "load_cached_market_full_context", lambda _: None
    )
    monkeypatch.setattr(
        market_state_module,
        "build_market_analysis_inputs",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        market_state_module,
        "build_market_theme_flow_context",
        lambda market, context, **kwargs: MarketContext(
            market_type=market, source="theme"
        ),
    )
    monkeypatch.setattr(market_state_module, "build_market_high_context", credit)
    monkeypatch.setattr(market_state_module, "build_market_option_snapshot", options)
    monkeypatch.setattr(
        market_state_module,
        "build_market_volatility_sentiment_context",
        lambda market, context, **kwargs: MarketContext(
            market_type=market, source="vol"
        ),
    )

    async def exercise():
        async for _ in state.refresh_market_details():
            pass

    asyncio.run(exercise())
    assert "credit" in applied
    assert "vol" in applied
    assert state.is_fetching_options is False


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
    assert state.ranked_themes[0].leader_ticker == "7203.T"
    assert state.ranked_themes[0].leader_performance == 1.0
    assert state.is_fetching is False


def test_theme_direction_and_sort_controls_preserve_coverage_semantics():
    state = ThemeState(_reflex_internal_init=True)
    state.ranked_themes = [
        ThemeItem(
            theme="High return",
            performance=5.0,
            coverage=55.0,
            stocks=[ThemeStock(ticker="AAA", performance=5.0)],
        ),
        ThemeItem(theme="High coverage", performance=2.0, coverage=95.0),
        ThemeItem(theme="Down one", performance=-1.0, coverage=60.0),
        ThemeItem(theme="Down two", performance=-4.0, coverage=90.0),
    ]

    assert [item.theme for item in state.top_10_themes] == [
        "High return",
        "High coverage",
    ]
    assert [item.theme for item in state.bottom_10_themes] == [
        "Down two",
        "Down one",
    ]

    state.set_sort_mode("coverage")
    state.set_direction_filter("down")

    assert [item.theme for item in state.top_10_themes] == [
        "High coverage",
        "High return",
    ]
    assert [item.theme for item in state.bottom_10_themes] == [
        "Down two",
        "Down one",
    ]
    assert state.show_upward_column is False
    assert state.show_downward_column is True
