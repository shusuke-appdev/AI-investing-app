"""Temporal alignment helpers for market data with explicit quality metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from src.persistent_cache import utc_now_iso
from src.services.analysis_context import DataResult

AsOfDirection = Literal["backward", "forward", "nearest"]

RIGHT_TIME_COLUMN = "_alignment_right_time"
MATCHED_COLUMN = "_alignment_matched"
DELTA_SECONDS_COLUMN = "_alignment_delta_seconds"


@dataclass
class TemporalAlignmentResult:
    """Aligned frame and retrieval-style status for UI and AI consumers."""

    frame: pd.DataFrame
    data_status: DataResult
    quality_warnings: list[str] = field(default_factory=list)

    @property
    def matched_count(self) -> int:
        if MATCHED_COLUMN not in self.frame.columns:
            return 0
        return int(self.frame[MATCHED_COLUMN].sum())

    @property
    def unmatched_count(self) -> int:
        return int(len(self.frame) - self.matched_count)


def align_temporal_asof(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    time_column: str = "timestamp",
    by: str | list[str] | None = None,
    tolerance: str | pd.Timedelta | None = None,
    direction: AsOfDirection = "backward",
    source: str = "temporal_alignment",
    name: str = "temporal_alignment",
) -> TemporalAlignmentResult:
    """Align `right` rows to `left` timestamps with an optional tolerance.

    This intentionally mirrors the Flint temporal-join idea without introducing
    Spark as a runtime dependency.
    """

    if left.empty:
        empty = left.copy()
        return TemporalAlignmentResult(
            frame=empty,
            data_status=DataResult(
                name=name,
                source=source,
                fetched_at=utc_now_iso(),
                cache_status="computed",
            ),
        )

    if right.empty:
        aligned = _mark_unmatched(left.copy(), time_column)
        warning = "Temporal alignment found no right-side rows to match."
        return TemporalAlignmentResult(
            frame=aligned,
            data_status=_build_status(
                name,
                source,
                unmatched_count=len(aligned),
                total_count=len(aligned),
                warnings=[warning],
            ),
            quality_warnings=[warning],
        )

    left_prepared = _prepare_frame(left, time_column)
    right_prepared = _prepare_frame(right, time_column)
    right_prepared[RIGHT_TIME_COLUMN] = right_prepared[time_column]

    merged = pd.merge_asof(
        left_prepared.sort_values(_sort_columns(time_column, by)),
        right_prepared.sort_values(_sort_columns(time_column, by)),
        on=time_column,
        by=by,
        tolerance=_coerce_tolerance(tolerance),
        direction=direction,
        suffixes=("", "_right"),
    ).sort_index()

    merged[MATCHED_COLUMN] = merged[RIGHT_TIME_COLUMN].notna()
    merged[DELTA_SECONDS_COLUMN] = _delta_seconds(
        merged[time_column], merged[RIGHT_TIME_COLUMN]
    )
    warnings = _quality_warnings(merged, tolerance)
    return TemporalAlignmentResult(
        frame=merged,
        data_status=_build_status(
            name,
            source,
            unmatched_count=int((~merged[MATCHED_COLUMN]).sum()),
            total_count=len(merged),
            warnings=warnings,
        ),
        quality_warnings=warnings,
    )


def _prepare_frame(frame: pd.DataFrame, time_column: str) -> pd.DataFrame:
    if time_column not in frame.columns:
        raise ValueError(f"Missing required time column: {time_column}")
    prepared = frame.copy()
    prepared[time_column] = pd.to_datetime(
        prepared[time_column], utc=True, errors="coerce"
    )
    if prepared[time_column].isna().any():
        raise ValueError(f"Invalid timestamps in column: {time_column}")
    return prepared


def _sort_columns(time_column: str, by: str | list[str] | None) -> list[str]:
    if by is None:
        return [time_column]
    if isinstance(by, str):
        return [by, time_column]
    return [*by, time_column]


def _coerce_tolerance(value: str | pd.Timedelta | None) -> pd.Timedelta | None:
    if value is None or isinstance(value, pd.Timedelta):
        return value
    return pd.Timedelta(value)


def _delta_seconds(left_time: pd.Series, right_time: pd.Series) -> pd.Series:
    return (left_time - right_time).abs().dt.total_seconds()


def _mark_unmatched(frame: pd.DataFrame, time_column: str) -> pd.DataFrame:
    prepared = _prepare_frame(frame, time_column)
    prepared[RIGHT_TIME_COLUMN] = pd.NaT
    prepared[MATCHED_COLUMN] = False
    prepared[DELTA_SECONDS_COLUMN] = pd.NA
    return prepared


def _quality_warnings(
    frame: pd.DataFrame, tolerance: str | pd.Timedelta | None
) -> list[str]:
    unmatched = int((~frame[MATCHED_COLUMN]).sum())
    if unmatched == 0:
        return []
    suffix = f" within tolerance {tolerance}" if tolerance is not None else ""
    return [f"Temporal alignment left {unmatched}/{len(frame)} rows unmatched{suffix}."]


def _build_status(
    name: str,
    source: str,
    *,
    unmatched_count: int,
    total_count: int,
    warnings: list[str],
) -> DataResult:
    return DataResult(
        name=name,
        source=source,
        fetched_at=utc_now_iso(),
        is_partial=unmatched_count > 0,
        error="; ".join(warnings),
        cache_status="computed",
        cache_age_seconds=None,
    )
