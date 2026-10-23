"""Validate new saved price observations at the Python import boundary."""

from __future__ import annotations

import math
from datetime import date


def validate_topdown(value: dict) -> None:
    if (
        not isinstance(value, dict)
        or value.get("version") != "topdown-v1"
        or value.get("market") not in {"US", "JP"}
    ):
        raise ValueError("Invalid topdown packet")
    for key in ("indices", "sectors", "distributions", "screening"):
        if not isinstance(value.get(key), list) or any(
            not isinstance(r, dict) for r in value[key]
        ):
            raise ValueError("Invalid topdown collection")
    seen = set()
    for row in value["screening"]:
        if (
            not isinstance(row.get("ticker"), str)
            or row["ticker"] in seen
            or row.get("market") != value["market"]
            or not isinstance(row.get("periods"), dict)
        ):
            raise ValueError("Invalid screening issuer")
        seen.add(row["ticker"])
        for flag in (
            row.get("stage2"),
            row.get("near_high"),
            row.get("vcp"),
            row.get("leader"),
            row.get("volume", {}).get("pocket_pivot"),
        ):
            if flag is not None and not isinstance(flag, bool):
                raise ValueError("Invalid screening condition")
        for period in row["periods"].values():
            for key in ("return", "relative_return"):
                number = period.get(key)
                if number is not None and (
                    isinstance(number, bool)
                    or not isinstance(number, (float, int))
                    or not math.isfinite(number)
                ):
                    raise ValueError("Invalid period return")
    sample = value.get("breadth")
    if not isinstance(sample, dict) or not isinstance(sample.get("history"), list):
        raise ValueError("Invalid breadth history")
    for row in sample["history"]:
        date.fromisoformat(row["date"])
        for key, counts in row["counts"].items():
            n, d = counts["numerator"], counts["denominator"]
            if (
                isinstance(n, bool)
                or isinstance(d, bool)
                or not isinstance(n, int)
                or not isinstance(d, int)
                or not 0 <= n <= d <= row["registered_count"]
            ):
                raise ValueError("Invalid breadth counts")
            number = row.get(key)
            if number is not None and (
                isinstance(number, bool)
                or not isinstance(number, (float, int))
                or not 0 <= number <= 100
                or not d
                or not math.isclose(number, n / d * 100)
            ):
                raise ValueError("Invalid breadth percentage")
