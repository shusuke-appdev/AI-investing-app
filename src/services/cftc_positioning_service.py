"""Point-in-time CFTC TFF positioning history for E-mini S&P 500 futures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import requests

from src.persistent_cache import repo_state_cache

CFTC_TFF_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
EMINI_SP500_CODE = "13874A"


@dataclass
class CftcPositioningResult:
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    status: str = "unavailable"
    source: str = "CFTC Traders in Financial Futures"
    as_of: str = ""
    is_stale: bool = False
    warnings: list[str] = field(default_factory=list)


def fetch_cftc_positioning(
    *,
    session: requests.Session | None = None,
    force_refresh: bool = False,
) -> CftcPositioningResult:
    """Fetch official weekly positions with a conservative publication lag."""

    cache = repo_state_cache("cftc_positioning")
    cached = cache.read("emini_sp500", fresh_seconds=24 * 3600, stale_seconds=7 * 86400)
    if cached.status == "fresh" and not force_refresh:
        return _result_from_records(cached.payload.get("records") or [])

    client = session or requests
    try:
        response = client.get(
            CFTC_TFF_URL,
            params={
                "$limit": 5000,
                "$where": f"cftc_contract_market_code='{EMINI_SP500_CODE}'",
                "$order": "report_date_as_yyyy_mm_dd ASC",
                "$select": ",".join(
                    (
                        "report_date_as_yyyy_mm_dd",
                        "open_interest_all",
                        "asset_mgr_positions_long",
                        "asset_mgr_positions_short",
                        "lev_money_positions_long",
                        "lev_money_positions_short",
                    )
                ),
            },
            headers={"User-Agent": "AI-investing-app/1.0"},
            timeout=15,
        )
        response.raise_for_status()
        records = response.json()
        result = _result_from_records(records)
        if result.data.empty:
            raise ValueError("empty CFTC positioning history")
        cache.write(
            "emini_sp500",
            {"records": records, "source": result.source},
        )
        return result
    except Exception as exc:
        if cached.is_available:
            result = _result_from_records(cached.payload.get("records") or [])
            result.is_stale = True
            result.status = "stale"
            result.warnings.append(f"CFTC refresh failed: {exc}")
            return result
        return CftcPositioningResult(warnings=[f"CFTC refresh failed: {exc}"])


def parse_cftc_positioning(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert report-date rows into features available only after publication."""

    frame = pd.DataFrame(records)
    if frame.empty or "report_date_as_yyyy_mm_dd" not in frame:
        return pd.DataFrame()
    frame["report_date"] = pd.to_datetime(
        frame["report_date_as_yyyy_mm_dd"], errors="coerce"
    ).dt.tz_localize(None)
    numeric = (
        "open_interest_all",
        "asset_mgr_positions_long",
        "asset_mgr_positions_short",
        "lev_money_positions_long",
        "lev_money_positions_short",
    )
    for column in numeric:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    frame = frame.dropna(subset=["report_date", "open_interest_all"])
    frame = frame.loc[frame["open_interest_all"] > 0].copy()
    frame["cftc_asset_manager_net_oi"] = (
        frame["asset_mgr_positions_long"] - frame["asset_mgr_positions_short"]
    ) / frame["open_interest_all"]
    frame["cftc_leveraged_money_net_oi"] = (
        frame["lev_money_positions_long"] - frame["lev_money_positions_short"]
    ) / frame["open_interest_all"]
    frame["available_date"] = (frame["report_date"] + pd.Timedelta(days=5)).map(
        pd.offsets.BDay().rollforward
    )
    output = frame.set_index("available_date")[
        [
            "cftc_asset_manager_net_oi",
            "cftc_leveraged_money_net_oi",
        ]
    ]
    return output.sort_index().loc[lambda item: ~item.index.duplicated(keep="last")]


def _result_from_records(records: list[dict[str, Any]]) -> CftcPositioningResult:
    frame = parse_cftc_positioning(records)
    return CftcPositioningResult(
        data=frame,
        status="available" if not frame.empty else "unavailable",
        as_of=str(frame.index.max().date()) if not frame.empty else "",
    )
