from src.marketdata_client import (
    MarketDataClient,
    MarketDataConfigError,
    MarketDataError,
)


class FakeResponse:
    def __init__(self, status_code, data=None, headers=None, text=""):
        self.status_code = status_code
        self._data = data
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        return self.response


def test_marketdata_client_requires_token(monkeypatch):
    monkeypatch.delenv("MARKETDATA_TOKEN", raising=False)

    try:
        MarketDataClient()
    except MarketDataConfigError as exc:
        assert "MARKETDATA_TOKEN" in str(exc)
    else:
        raise AssertionError("Expected missing-token error")


def test_marketdata_client_accepts_203_and_bearer_header():
    session = FakeSession(
        FakeResponse(
            203,
            {"s": "ok", "strike": [100]},
            {"X-Api-Credits-Consumed": "2", "X-Api-Credits-Remaining": "98"},
        )
    )
    client = MarketDataClient("secret", session=session)

    result = client.get("/options/chain/SPY/", {"dte": 0})

    assert session.headers["Authorization"] == "Bearer secret"
    assert result.status_code == 203
    assert result.credits_consumed == 2
    assert result.credits_remaining == 98


def test_marketdata_client_treats_204_as_no_data():
    client = MarketDataClient("secret", session=FakeSession(FakeResponse(204)))

    result = client.get("/options/chain/SPY/")

    assert result.data == {"s": "no_data"}


def test_marketdata_client_raises_api_error():
    client = MarketDataClient(
        "secret",
        session=FakeSession(FakeResponse(200, {"s": "error", "errmsg": "bad request"})),
    )

    try:
        client.get("/options/chain/SPY/")
    except MarketDataError as exc:
        assert "bad request" in str(exc)
    else:
        raise AssertionError("Expected API error")
