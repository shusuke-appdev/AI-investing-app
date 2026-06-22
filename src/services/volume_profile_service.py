"""Approximate price-by-volume profiles from daily OHLCV bars."""

from __future__ import annotations

from typing import Any

import pandas as pd

LOOKBACK_SESSIONS = 126
MIN_SESSIONS = 60
PRICE_BINS = 24
VALUE_AREA_RATIO = 0.70


def build_volume_profile(
    frame: pd.DataFrame | None,
    *,
    current_price: float | None = None,
    lookback: int = LOOKBACK_SESSIONS,
    bins: int = PRICE_BINS,
    min_sessions: int = MIN_SESSIONS,
) -> dict[str, Any]:
    """Distribute each daily volume uniformly across its high-low price range."""

    normalized = _normalize(frame).tail(lookback)
    if len(normalized) < min_sessions:
        return _unavailable(
            f"最低{min_sessions}営業日が必要です（取得={len(normalized)}営業日）。",
            sessions=len(normalized),
            bins=bins,
        )

    price_low = float(normalized["Low"].min())
    price_high = float(normalized["High"].max())
    if price_high <= price_low or bins <= 0:
        return _unavailable("有効な価格レンジを作成できません。", len(normalized), bins)

    width = (price_high - price_low) / bins
    volumes = [0.0] * bins
    for row in normalized.itertuples(index=False):
        day_low = max(price_low, float(row.Low))
        day_high = min(price_high, float(row.High))
        day_volume = max(0.0, float(row.Volume))
        if day_volume <= 0:
            continue
        if day_high <= day_low:
            index = min(bins - 1, max(0, int((day_low - price_low) / width)))
            volumes[index] += day_volume
            continue
        overlaps = []
        for index in range(bins):
            bin_low = price_low + index * width
            bin_high = bin_low + width
            overlap = max(0.0, min(day_high, bin_high) - max(day_low, bin_low))
            overlaps.append(overlap)
        overlap_total = sum(overlaps)
        if overlap_total <= 0:
            continue
        for index, overlap in enumerate(overlaps):
            volumes[index] += day_volume * overlap / overlap_total

    total_volume = sum(volumes)
    if total_volume <= 0:
        return _unavailable("有効な出来高を取得できません。", len(normalized), bins)

    poc_index = max(range(bins), key=volumes.__getitem__)
    value_indices = _value_area_indices(volumes, poc_index, VALUE_AREA_RATIO)
    value_low_index = min(value_indices)
    value_high_index = max(value_indices)
    max_volume = max(volumes)
    rows = []
    for index, volume in enumerate(volumes):
        bin_low = price_low + index * width
        bin_high = price_low + (index + 1) * width
        rows.append(
            {
                "index": index,
                "low": round(bin_low, 4),
                "high": round(bin_high, 4),
                "volume": round(volume, 2),
                "share": round(volume / total_volume, 4),
                "relative_volume": round(volume / max_volume, 4),
                "is_poc": index == poc_index,
                "in_value_area": index in value_indices,
            }
        )

    latest = _number(current_price) or float(normalized["Close"].iloc[-1])
    concentration_indices = _concentration_indices(volumes)
    concentration_zones = [_zone(rows[index]) for index in concentration_indices]
    support = _nearest_zone(rows, concentration_indices, latest, below=True)
    resistance = _nearest_zone(rows, concentration_indices, latest, below=False)

    return {
        "status": "available",
        "method": "daily_high_low_uniform_distribution",
        "lookback_sessions": len(normalized),
        "requested_lookback_sessions": lookback,
        "bin_count": bins,
        "value_area_ratio": VALUE_AREA_RATIO,
        "price_range": {"low": round(price_low, 4), "high": round(price_high, 4)},
        "poc": _zone(rows[poc_index]),
        "value_area": {
            "val": round(float(rows[value_low_index]["low"]), 4),
            "vah": round(float(rows[value_high_index]["high"]), 4),
        },
        "concentration_zones": concentration_zones,
        "support_zone": support,
        "resistance_zone": resistance,
        "current_price": round(latest, 4),
        "bins": rows,
        "summary": _summary(rows[poc_index], support, resistance),
        "limitations": [
            "日足の各出来高を安値から高値へ均等配分した近似値です。",
            "取引所約定別の実測Volume Profileではありません。",
        ],
    }


def _normalize(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["High", "Low", "Close", "Volume"])
    columns = {str(column).lower(): column for column in frame.columns}
    required = {}
    for name in ("high", "low", "close", "volume"):
        if name not in columns:
            return pd.DataFrame(columns=["High", "Low", "Close", "Volume"])
        required[columns[name]] = name.title()
    normalized = frame[list(required)].rename(columns=required).copy()
    for column in ("High", "Low", "Close", "Volume"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=["High", "Low", "Close", "Volume"])
    return normalized[
        (normalized["High"] >= normalized["Low"]) & (normalized["Volume"] >= 0)
    ]


def _value_area_indices(
    volumes: list[float], poc_index: int, target_ratio: float
) -> set[int]:
    selected = {poc_index}
    selected_volume = volumes[poc_index]
    target = sum(volumes) * target_ratio
    lower = poc_index - 1
    upper = poc_index + 1
    while selected_volume < target and (lower >= 0 or upper < len(volumes)):
        lower_volume = volumes[lower] if lower >= 0 else -1.0
        upper_volume = volumes[upper] if upper < len(volumes) else -1.0
        if upper_volume > lower_volume:
            selected.add(upper)
            selected_volume += upper_volume
            upper += 1
        else:
            selected.add(lower)
            selected_volume += lower_volume
            lower -= 1
    return selected


def _concentration_indices(volumes: list[float]) -> list[int]:
    ordered = sorted(range(len(volumes)), key=volumes.__getitem__, reverse=True)
    threshold = max(volumes) * 0.70
    selected = [
        index
        for index in ordered
        if volumes[index] >= threshold
        and (index == 0 or volumes[index] >= volumes[index - 1])
        and (index == len(volumes) - 1 or volumes[index] >= volumes[index + 1])
    ]
    return sorted((selected or ordered[:3])[:5])


def _nearest_zone(
    rows: list[dict[str, Any]],
    indices: list[int],
    current_price: float,
    *,
    below: bool,
) -> dict[str, float] | None:
    candidates = []
    for index in indices:
        row = rows[index]
        midpoint = (float(row["low"]) + float(row["high"])) / 2
        if (below and midpoint <= current_price) or (
            not below and midpoint >= current_price
        ):
            candidates.append((abs(midpoint - current_price), row))
    return _zone(min(candidates, key=lambda item: item[0])[1]) if candidates else None


def _zone(row: dict[str, Any]) -> dict[str, float]:
    return {
        "low": round(float(row["low"]), 4),
        "high": round(float(row["high"]), 4),
        "share": round(float(row["share"]), 4),
    }


def _summary(
    poc: dict[str, Any],
    support: dict[str, float] | None,
    resistance: dict[str, float] | None,
) -> str:
    parts = [f"POC {poc['low']:.2f}～{poc['high']:.2f}"]
    if support:
        parts.append(f"支持 {support['low']:.2f}～{support['high']:.2f}")
    if resistance:
        parts.append(f"抵抗 {resistance['low']:.2f}～{resistance['high']:.2f}")
    return " / ".join(parts)


def _unavailable(reason: str, sessions: int, bins: int) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "lookback_sessions": sessions,
        "bin_count": bins,
        "summary": "価格帯別出来高は算出不可です。",
        "reason": reason,
        "bins": [],
    }


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None
