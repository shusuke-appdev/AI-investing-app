"""Presentation formatting for Market Intelligence state."""

from __future__ import annotations

from typing import Any


def format_option_summaries(option_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return Reflex-safe option summary dictionaries."""

    formatted: list[dict[str, Any]] = []
    for opt in option_data:
        pcr = opt.get("pcr") or {}
        gex = opt.get("gex")
        pcr_val = float(pcr.get("volume_pcr", 0.0))
        has_gex = isinstance(gex, dict) and gex.get("nearby_net_gex") is not None
        gex_val = float(gex.get("nearby_net_gex", 0.0)) if has_gex else 0.0
        current_price = float(opt.get("current_price") or 0.0)
        iv_val = opt.get("iv")
        max_pain = opt.get("max_pain")
        formatted.append(
            {
                "ticker": opt.get("ticker", ""),
                "sentiment": opt.get("sentiment", "Neutral"),
                "current_price": current_price,
                "current_price_str": f"${current_price:,.2f}"
                if current_price > 0
                else "",
                "pcr_vol": pcr_val,
                "pcr_vol_str": f"{pcr_val:.2f}",
                "net_gex": gex_val,
                "net_gex_str": f"{gex_val / 1e6:+.0f}M" if has_gex else "-",
                "net_gex_available": has_gex,
                "iv": f"{iv_val * 100:.1f}%" if iv_val is not None else "-",
                "max_pain": f"${max_pain:.0f}" if max_pain is not None else "-",
                "analysis": opt.get("analysis", []),
                "data_quality": opt.get("data_quality", "unavailable"),
                "quality_warnings": list(opt.get("quality_warnings") or []),
            }
        )
    return formatted
