"""Small REST client for MarketData.app."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import requests


class MarketDataError(Exception):
    """Base error for MarketData.app requests."""


class MarketDataConfigError(MarketDataError):
    """Raised when MarketData.app authentication is not configured."""


@dataclass(frozen=True)
class MarketDataResponse:
    """Normalized HTTP response plus credit metadata."""

    data: dict[str, Any]
    status_code: int
    credits_consumed: int | None = None
    credits_remaining: int | None = None
    credits_reset_at: str = ""
    headers: dict[str, str] = field(default_factory=dict)


class MarketDataClient:
    """Bearer-authenticated MarketData.app REST client."""

    BASE_URL = "https://api.marketdata.app/v1"

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout: int = 30,
        session: requests.Session | None = None,
    ) -> None:
        self.token = token or os.getenv("MARKETDATA_TOKEN", "").strip()
        if not self.token:
            raise MarketDataConfigError("MARKETDATA_TOKEN is not configured.")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
        )

    def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> MarketDataResponse:
        response = self.session.get(
            f"{self.BASE_URL}{path}",
            params=params or {},
            timeout=self.timeout,
        )
        headers = {str(key): str(value) for key, value in response.headers.items()}
        credits = _credit_metadata(headers)

        if response.status_code == 204:
            return MarketDataResponse(
                data={"s": "no_data"},
                status_code=204,
                headers=headers,
                **credits,
            )
        if response.status_code not in (200, 203):
            raise MarketDataError(
                f"MarketData.app HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise MarketDataError("MarketData.app returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise MarketDataError("MarketData.app returned a non-object response.")
        if data.get("s") == "error":
            raise MarketDataError(
                str(data.get("errmsg") or "MarketData.app API error.")
            )

        return MarketDataResponse(
            data=data,
            status_code=response.status_code,
            headers=headers,
            **credits,
        )


def is_configured() -> bool:
    """Return whether a MarketData.app token is available."""

    return bool(os.getenv("MARKETDATA_TOKEN", "").strip())


def _credit_metadata(headers: dict[str, str]) -> dict[str, Any]:
    lowered = {key.lower(): value for key, value in headers.items()}
    return {
        "credits_consumed": _optional_int(
            _first_header(
                lowered,
                "x-api-credits-consumed",
                "x-credits-consumed",
                "x-ratelimit-used",
            )
        ),
        "credits_remaining": _optional_int(
            _first_header(
                lowered,
                "x-api-credits-remaining",
                "x-credits-remaining",
                "x-ratelimit-remaining",
            )
        ),
        "credits_reset_at": _first_header(
            lowered,
            "x-api-credits-reset",
            "x-credits-reset",
            "x-ratelimit-reset",
        ),
    }


def _first_header(headers: dict[str, str], *names: str) -> str:
    for name in names:
        value = headers.get(name)
        if value:
            return value
    return ""


def _optional_int(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None
