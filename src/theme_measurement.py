"""Theme measurement baskets kept separate from the full membership taxonomy."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from src.theme_taxonomy import get_theme_profile
from src.themes_config import get_themes

MEASUREMENT_VERSION_PATH = (
    Path(__file__).resolve().parent / "data" / "theme_measurement_baskets_v1.json"
)


class ThemeMeasurementBasket(TypedDict):
    """Runtime basket used to measure one configured theme."""

    theme: str
    market_type: str
    all_tickers: list[str]
    measurement_tickers: list[str]
    proxy_ticker: str
    method: str
    reduced: bool


def get_theme_measurement_baskets(
    market_type: str = "US",
) -> dict[str, ThemeMeasurementBasket]:
    """Return conservative baskets without changing stock-to-theme membership.

    Only an offline-audited, versioned selection may reduce a basket. When that
    evidence is absent or invalid, the runtime keeps every configured member.
    """

    market = "JP" if market_type.upper() == "JP" else "US"
    versioned = _versioned_baskets().get(market, {})
    result: dict[str, ThemeMeasurementBasket] = {}
    for theme, configured in get_themes(market).items():
        members = list(dict.fromkeys(str(ticker).upper() for ticker in configured))
        profile = get_theme_profile(theme, market, tickers=members)
        audited = versioned.get(theme, [])
        measurement = [ticker for ticker in audited if ticker in members]
        if not measurement or len(measurement) != len(audited):
            measurement = list(members)
        result[theme] = {
            "theme": theme,
            "market_type": market,
            "all_tickers": members,
            "measurement_tickers": measurement,
            "proxy_ticker": profile.proxy_ticker,
            "method": (
                "all_configured_fallback"
                if len(measurement) == len(members)
                else "offline_audited_v1"
            ),
            "reduced": len(measurement) < len(members),
        }
    return result


@lru_cache(maxsize=1)
def _versioned_baskets() -> dict[str, dict[str, list[str]]]:
    if not MEASUREMENT_VERSION_PATH.exists():
        return {}
    try:
        payload = json.loads(MEASUREMENT_VERSION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if payload.get("audit_passed") is not True:
        return {}
    markets = payload.get("markets")
    if not isinstance(markets, dict):
        return {}
    result: dict[str, dict[str, list[str]]] = {}
    for market, data in markets.items():
        baskets = data.get("baskets") if isinstance(data, dict) else None
        if not isinstance(baskets, dict):
            continue
        result[str(market)] = {
            str(theme): [str(ticker).upper() for ticker in tickers]
            for theme, tickers in baskets.items()
            if isinstance(tickers, list)
        }
    return result


def measurement_universe(market_type: str = "US") -> list[str]:
    """Return a stable, deduplicated runtime measurement universe."""

    seen: set[str] = set()
    result: list[str] = []
    for basket in get_theme_measurement_baskets(market_type).values():
        for ticker in [*basket["measurement_tickers"], basket["proxy_ticker"]]:
            if ticker and ticker not in seen:
                seen.add(ticker)
                result.append(ticker)
    return result
