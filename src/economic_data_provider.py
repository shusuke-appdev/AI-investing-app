"""FRED economic series retrieval with pandas-datareader recovery and cache."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from typing import Any
from zipfile import ZipFile, is_zipfile

import pandas as pd
import requests

from src.pandas_datareader_compat import import_pandas_datareader_data
from src.persistent_cache import PersistentJsonCache, repo_state_cache, utc_now_iso
from src.provider_result import FetchResult

ECONOMIC_DATA_CACHE_NAMESPACE = "economic_data_cache"
FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
DEFAULT_FRESH_SECONDS = 12 * 60 * 60
DEFAULT_STALE_SECONDS = 14 * 24 * 60 * 60
DEFAULT_FRED_CSV_TIMEOUT = 12


@dataclass
class EconomicDataResult(FetchResult[pd.DataFrame]):
    """Economic time series plus source/status metadata."""

    data: pd.DataFrame = field(default_factory=pd.DataFrame)


def fetch_fred_series(
    series_ids: list[str] | tuple[str, ...],
    *,
    start: datetime | str | None = None,
    end: datetime | str | None = None,
    fresh_seconds: int = DEFAULT_FRESH_SECONDS,
    stale_seconds: int = DEFAULT_STALE_SECONDS,
    prefer_stale_cache: bool = False,
    csv_timeout: int = DEFAULT_FRED_CSV_TIMEOUT,
    use_pandas_datareader_fallback: bool = True,
) -> EconomicDataResult:
    """Fetch FRED series with fresh-cache reuse and stale fallback."""

    ids = [str(item).strip().upper() for item in series_ids if str(item).strip()]
    if not ids:
        return EconomicDataResult(
            error="FRED系列IDが指定されていません。", is_partial=True
        )

    cache = _economic_cache()
    key = _cache_key(ids, start, end)
    cached = cache.read(key, fresh_seconds=fresh_seconds, stale_seconds=stale_seconds)
    if cached.status == "fresh":
        return _result_from_cache(cached)
    if prefer_stale_cache and cached.is_available:
        result = _result_from_cache(cached)
        result.is_partial = True
        result.warnings = [
            *result.warnings,
            "FREDのライブ更新を待たず、保存済みデータを表示しています。",
        ]
        result.error = "; ".join(result.warnings)
        return result

    warnings: list[str] = []
    try:
        frame = _fetch_with_fred_csv(ids, start, end, timeout=csv_timeout)
        source = "fred_csv"
    except Exception as exc:
        warnings.append(f"FRED CSV取得失敗: {exc}")
        if cached.is_available and prefer_stale_cache:
            result = _result_from_cache(cached)
            result.warnings = [*result.warnings, *warnings]
            result.error = "; ".join(warnings)
            result.is_partial = True
            return result
        if not use_pandas_datareader_fallback:
            if cached.is_available:
                result = _result_from_cache(cached)
                result.warnings = [*result.warnings, *warnings]
                result.error = "; ".join(warnings)
                result.is_partial = True
                return result
            return EconomicDataResult(
                source="failed",
                fetched_at=utc_now_iso(),
                is_partial=True,
                cache_status="failed",
                warnings=warnings,
                error="; ".join(warnings),
            )
        try:
            frame = _fetch_with_pandas_datareader(ids, start, end)
            source = "pandas_datareader"
        except Exception as pdr_exc:
            warnings.append(f"pandas_datareader代替取得失敗: {pdr_exc}")
            if cached.is_available:
                result = _result_from_cache(cached)
                result.warnings = [*result.warnings, *warnings]
                result.error = "; ".join(warnings)
                result.is_partial = True
                return result
            return EconomicDataResult(
                source="failed",
                fetched_at=utc_now_iso(),
                is_partial=True,
                cache_status="failed",
                warnings=warnings,
                error="; ".join(warnings),
            )

    result = EconomicDataResult(
        data=frame,
        source=source,
        fetched_at=utc_now_iso(),
        is_partial=frame.empty or any(item not in frame.columns for item in ids),
        cache_status="live",
        warnings=warnings,
        error="; ".join(warnings),
    )
    if not frame.empty:
        cache.write(
            key,
            _payload_from_frame(frame, ids, source, warnings),
            fetched_at=result.fetched_at,
        )
    return result


def _fetch_with_pandas_datareader(
    series_ids: list[str],
    start: datetime | str | None,
    end: datetime | str | None,
) -> pd.DataFrame:
    pdr_data = import_pandas_datareader_data()
    frame = pdr_data.DataReader(
        series_ids, "fred", _coerce_start(start), _coerce_end(end)
    )
    return _normalize_frame(frame, series_ids)


def _fetch_with_fred_csv(
    series_ids: list[str],
    start: datetime | str | None,
    end: datetime | str | None,
    *,
    timeout: int,
) -> pd.DataFrame:
    params = {"id": ",".join(series_ids)}
    start_dt = _coerce_datetime(start)
    end_dt = _coerce_datetime(end)
    if start_dt is not None:
        params["cosd"] = start_dt.date().isoformat()
    if end_dt is not None:
        params["coed"] = end_dt.date().isoformat()
    response = requests.get(
        FRED_GRAPH_CSV_URL,
        params=params,
        headers={"User-Agent": "AI-investing-app/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()

    frames = (
        _frames_from_fred_zip(response.content, series_ids)
        if is_zipfile(BytesIO(response.content))
        else _frames_from_fred_text(response.text, series_ids)
    )
    if not frames:
        raise ValueError("FRED CSV response did not contain requested series.")
    combined = pd.concat(frames, axis=1).sort_index()
    return _filter_dates(_normalize_frame(combined, series_ids), start, end)


def _frames_from_fred_zip(content: bytes, series_ids: list[str]) -> list[pd.DataFrame]:
    frames = []
    with ZipFile(BytesIO(content)) as archive:
        for name in archive.namelist():
            if name.endswith(".csv"):
                frames.extend(
                    _frames_from_fred_table(pd.read_csv(archive.open(name)), series_ids)
                )
    return frames


def _frames_from_fred_text(text: str, series_ids: list[str]) -> list[pd.DataFrame]:
    return _frames_from_fred_table(pd.read_csv(StringIO(text)), series_ids)


def _frames_from_fred_table(
    frame: pd.DataFrame, series_ids: list[str]
) -> list[pd.DataFrame]:
    if "observation_date" not in frame.columns:
        return []
    frame["observation_date"] = pd.to_datetime(frame["observation_date"])
    result = []
    for series_id in series_ids:
        if series_id not in frame.columns:
            continue
        frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce")
        result.append(frame.set_index("observation_date")[[series_id]])
    return result


def _normalize_frame(frame: pd.DataFrame, series_ids: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=series_ids)
    normalized = frame.copy()
    normalized.index = pd.to_datetime(normalized.index)
    normalized = normalized.sort_index()
    for series_id in series_ids:
        if series_id in normalized.columns:
            normalized[series_id] = pd.to_numeric(
                normalized[series_id], errors="coerce"
            )
    return normalized


def _filter_dates(
    frame: pd.DataFrame,
    start: datetime | str | None,
    end: datetime | str | None,
) -> pd.DataFrame:
    if frame.empty:
        return frame
    filtered = frame
    start_dt = _coerce_datetime(start)
    end_dt = _coerce_datetime(end)
    if start_dt is not None:
        filtered = filtered[filtered.index >= start_dt]
    if end_dt is not None:
        filtered = filtered[filtered.index <= end_dt]
    return filtered


def _payload_from_frame(
    frame: pd.DataFrame,
    series_ids: list[str],
    source: str,
    warnings: list[str],
) -> dict[str, Any]:
    records = []
    for date, row in frame.iterrows():
        item: dict[str, Any] = {"date": date.date().isoformat()}
        for series_id in series_ids:
            value = row.get(series_id)
            item[series_id] = None if pd.isna(value) else float(value)
        records.append(item)
    return {
        "series_ids": series_ids,
        "records": records,
        "source": source,
        "warnings": warnings,
    }


def _result_from_cache(read) -> EconomicDataResult:
    records = list(read.payload.get("records") or [])
    frame = pd.DataFrame(records)
    if not frame.empty and "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date").sort_index()
        for column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return EconomicDataResult(
        data=frame,
        source=str(read.payload.get("source") or "cache"),
        fetched_at=read.fetched_at,
        is_stale=read.is_stale,
        is_partial=frame.empty,
        cache_status="stale_cache" if read.is_stale else "persistent_cache",
        cache_age_seconds=read.age_seconds,
        warnings=list(read.payload.get("warnings") or []),
    )


def _cache_key(
    series_ids: list[str],
    start: datetime | str | None,
    end: datetime | str | None,
) -> str:
    start_text = (
        _coerce_datetime(start).date().isoformat()
        if _coerce_datetime(start)
        else "none"
    )
    end_text = (
        _coerce_datetime(end).date().isoformat() if _coerce_datetime(end) else "none"
    )
    return "_".join(series_ids) + f"_{start_text}_{end_text}"


def _coerce_start(value: datetime | str | None) -> datetime:
    return _coerce_datetime(value) or datetime.now(timezone.utc).replace(
        tzinfo=None
    ) - timedelta(days=365 * 10)


def _coerce_end(value: datetime | str | None) -> datetime:
    return _coerce_datetime(value) or datetime.now(timezone.utc).replace(tzinfo=None)


def _coerce_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return pd.to_datetime(value).to_pydatetime().replace(tzinfo=None)


def _economic_cache() -> PersistentJsonCache:
    return repo_state_cache(ECONOMIC_DATA_CACHE_NAMESPACE)
