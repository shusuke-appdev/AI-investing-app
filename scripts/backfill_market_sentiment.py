"""Backfill official OCC put/call history for composite market sentiment."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    from src.services.occ_put_call_service import backfill_occ_put_call_history

    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="SPY,QQQ")
    parser.add_argument("--sessions", type=int, default=252)
    args = parser.parse_args()
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    end = pd.Timestamp(datetime.now(timezone.utc).date()) - pd.offsets.BDay(1)
    dates = [item.date() for item in pd.bdate_range(end=end, periods=args.sessions)]
    failed = False
    for symbol in symbols:
        result = backfill_occ_put_call_history(symbol, dates)
        print(
            f"{symbol}: status={result.status} rows={len(result.history)} "
            f"as_of={result.as_of} warnings={len(result.warnings)}"
        )
        failed = failed or result.status == "unavailable"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
