"""Generate versioned theme measurement baskets after a two-year bias audit."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.theme_measurement_audit_service import (  # noqa: E402
    build_audited_measurement_baskets,
)
from src.themes_config import get_themes  # noqa: E402
from src.yfinance_runtime import configure_yfinance_cache  # noqa: E402

DEFAULT_OUTPUT = ROOT / "src" / "data" / "theme_measurement_baskets_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=("US", "JP", "both"), default="both")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    configure_yfinance_cache()
    markets = ("US", "JP") if args.market == "both" else (args.market,)
    results = {}
    all_passed = True
    for market in markets:
        themes = get_themes(market)
        tickers = list(
            dict.fromkeys(ticker for values in themes.values() for ticker in values)
        )
        raw = yf.download(
            tickers,
            period="2y",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
            timeout=30,
        )
        frames = {
            ticker: frame
            for ticker in tickers
            if not (frame := _extract_ticker_frame(raw, ticker, tickers)).empty
        }
        audit = build_audited_measurement_baskets(
            themes=themes,
            price_frames=frames,
        )
        results[market] = {
            "baskets": audit["baskets"],
            "audit": {
                key: value
                for key, value in audit.items()
                if key not in {"baskets", "theme_audits"}
            },
            "theme_audits": audit["theme_audits"],
            "fetched_tickers": len(frames),
            "requested_tickers": len(tickers),
        }
        all_passed = all_passed and bool(audit["passed"])
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "two_year_rolling_return_and_cross_section_rank_audit",
        "audit_passed": all_passed,
        "markets": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"audit_passed": all_passed, "output": str(args.output)}))
    return 0 if all_passed else 2


def _extract_ticker_frame(
    raw: pd.DataFrame, ticker: str, request_tickers: list[str]
) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy() if len(request_tickers) == 1 else pd.DataFrame()
    first = raw.columns.get_level_values(0)
    second = raw.columns.get_level_values(1)
    if ticker in first:
        return raw[ticker].dropna(how="all")
    if ticker in second:
        return raw.xs(ticker, axis=1, level=1).dropna(how="all")
    return pd.DataFrame()


if __name__ == "__main__":
    raise SystemExit(main())
