"""Official OCC option-volume put/call history with repo-local persistence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from typing import Any

import pandas as pd
import requests

from src.persistent_cache import repo_state_cache, utc_now_iso

OCC_VOLUME_URL = "https://marketdata.theocc.com/volume-query"
OCC_HISTORY_STALE_SECONDS = 10 * 365 * 86400


@dataclass
class OccPutCallResult:
    symbol: str
    history: pd.DataFrame = field(default_factory=pd.DataFrame)
    status: str = "unavailable"
    source: str = "OCC consolidated option volume"
    as_of: str = ""
    warnings: list[str] = field(default_factory=list)


def load_occ_put_call_history(symbol: str) -> OccPutCallResult:
    """Load previously captured official OCC daily put/call observations."""

    normalized = symbol.upper().strip()
    cached = repo_state_cache("occ_put_call_history").read(
        normalized.lower(),
        fresh_seconds=86400,
        stale_seconds=OCC_HISTORY_STALE_SECONDS,
    )
    frame = _frame_from_records(cached.payload.get("records") or [])
    return _result(normalized, frame)


def refresh_occ_put_call_latest(
    symbol: str,
    *,
    today: date | None = None,
    session: requests.Session | None = None,
) -> OccPutCallResult:
    """Fetch the most recent available completed OCC report without bulk backfill."""

    normalized = symbol.upper().strip()
    existing = load_occ_put_call_history(normalized).history
    end = today or datetime.now(timezone.utc).date()
    warnings: list[str] = []
    for offset in range(1, 8):
        report_date = end - timedelta(days=offset)
        if report_date.weekday() >= 5:
            continue
        try:
            row = fetch_occ_put_call_day(normalized, report_date, session=session)
        except Exception as exc:
            warnings.append(f"{report_date.isoformat()}: {exc}")
            continue
        if row is None:
            continue
        combined = _merge_history(existing, pd.DataFrame([row]))
        _save_history(normalized, combined)
        result = _result(normalized, combined)
        result.warnings = warnings
        return result
    result = _result(normalized, existing)
    result.warnings = warnings or ["No recent OCC daily report was available."]
    return result


def backfill_occ_put_call_history(
    symbol: str,
    report_dates: Iterable[date],
    *,
    session: requests.Session | None = None,
) -> OccPutCallResult:
    """Fetch selected report dates, reusing existing observations for resumability."""

    normalized = symbol.upper().strip()
    existing = load_occ_put_call_history(normalized).history
    existing_dates = {
        item.date() for item in existing.index if isinstance(item, pd.Timestamp)
    }
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for report_date in report_dates:
        if report_date in existing_dates or report_date.weekday() >= 5:
            continue
        try:
            row = fetch_occ_put_call_day(normalized, report_date, session=session)
        except Exception as exc:
            warnings.append(f"{report_date.isoformat()}: {exc}")
            continue
        if row is not None:
            rows.append(row)
    additions = pd.DataFrame(rows)
    combined = _merge_history(existing, additions)
    if not combined.empty:
        _save_history(normalized, combined)
    result = _result(normalized, combined)
    result.warnings = warnings
    return result


def fetch_occ_put_call_day(
    symbol: str,
    report_date: date,
    *,
    session: requests.Session | None = None,
) -> dict[str, Any] | None:
    """Fetch and aggregate one official OCC daily option-volume report."""

    normalized = symbol.upper().strip()
    date_text = report_date.strftime("%Y%m%d")
    client = session or requests
    response = client.get(
        OCC_VOLUME_URL,
        params={
            "reportDate": date_text,
            "format": "csv",
            "volumeQueryType": "O",
            "symbolType": "O",
            "symbol": normalized,
            "reportType": "D",
            "accountType": "ALL",
            "productKind": "OSTK",
            "porc": "BOTH",
            "contractDt": date_text,
        },
        headers={"User-Agent": "AI-investing-app/1.0"},
        timeout=12,
    )
    response.raise_for_status()
    return _parse_occ_volume_csv(response.text, normalized, report_date)


def _parse_occ_volume_csv(
    text: str, symbol: str, report_date: date
) -> dict[str, Any] | None:
    frame = pd.read_csv(StringIO(text))
    required = {"quantity", "porc"}
    if frame.empty or not required.issubset(frame.columns):
        return None
    quantity = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0.0)
    side = frame["porc"].astype(str).str.upper()
    calls = float(quantity[side == "C"].sum())
    puts = float(quantity[side == "P"].sum())
    if calls <= 0 and puts <= 0:
        return None
    return {
        "date": report_date.isoformat(),
        "symbol": symbol,
        "calls": int(calls),
        "puts": int(puts),
        "put_call_ratio": round(puts / calls, 6) if calls > 0 else None,
        "source": "OCC consolidated option volume",
    }


def _frame_from_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if frame.empty or "date" not in frame:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ("calls", "puts", "put_call_ratio"):
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    return frame.dropna(subset=["date"]).set_index("date").sort_index()


def _merge_history(existing: pd.DataFrame, additions: pd.DataFrame) -> pd.DataFrame:
    if not additions.empty and "date" in additions:
        additions = additions.copy()
        additions["date"] = pd.to_datetime(additions["date"], errors="coerce")
        additions = additions.dropna(subset=["date"]).set_index("date")
    frames = [frame for frame in (existing, additions) if not frame.empty]
    if not frames:
        return pd.DataFrame()
    return (
        pd.concat(frames, axis=0, sort=False)
        .sort_index()
        .loc[lambda frame: ~frame.index.duplicated(keep="last")]
    )


def _save_history(symbol: str, frame: pd.DataFrame) -> None:
    records = []
    for index, row in frame.iterrows():
        records.append(
            {
                "date": str(pd.Timestamp(index).date()),
                "symbol": symbol,
                "calls": _optional_int(row.get("calls")),
                "puts": _optional_int(row.get("puts")),
                "put_call_ratio": _optional_float(row.get("put_call_ratio")),
                "source": "OCC consolidated option volume",
            }
        )
    repo_state_cache("occ_put_call_history").write(
        symbol.lower(),
        {"records": records, "source": "OCC consolidated option volume"},
        fetched_at=utc_now_iso(),
    )


def _result(symbol: str, frame: pd.DataFrame) -> OccPutCallResult:
    as_of = str(frame.index.max().date()) if not frame.empty else ""
    status = "available" if len(frame) >= 60 else "insufficient_data"
    if frame.empty:
        status = "unavailable"
    return OccPutCallResult(symbol=symbol, history=frame, status=status, as_of=as_of)


def _optional_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(number) else number


def _optional_int(value: Any) -> int | None:
    number = _optional_float(value)
    return int(number) if number is not None else None
