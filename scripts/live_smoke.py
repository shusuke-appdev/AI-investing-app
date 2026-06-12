"""Live integration smoke checks with cleanup and explicit skip boundaries."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv()


@dataclass
class Check:
    name: str
    status: str
    detail: str


def _run(name: str, callback: Callable[[], str]) -> Check:
    try:
        detail = callback()
        status = (
            "SKIP"
            if detail.startswith("SKIP:")
            else "DEGRADED"
            if detail.startswith("DEGRADED:")
            else "PASS"
        )
        return Check(name, status, detail)
    except Exception as exc:
        return Check(name, "FAIL", str(exc))


def _external_market_check() -> str:
    from src.market_data import get_stock_data

    frame = get_stock_data("SPY", "5d")
    if frame is None or frame.empty:
        raise RuntimeError("SPY price history is empty")
    return f"SPY rows={len(frame)}"


def _fred_check() -> str:
    from src.economic_data_provider import fetch_fred_series

    result = fetch_fred_series(
        ["BAA10Y"],
        csv_timeout=30,
        fresh_seconds=0,
        use_pandas_datareader_fallback=False,
    )
    if result.data.empty:
        from src.credit_stress_monitor import build_credit_stress_monitor

        fallback = build_credit_stress_monitor("US")
        if fallback.get("status") and fallback.get("status") != "unavailable":
            return (
                "DEGRADED: live FRED unavailable; app credit-stress path recovered "
                f"with status={fallback.get('status')}, source={fallback.get('source')}"
            )
        raise RuntimeError(result.error or "FRED BAA10Y is empty")
    return f"source={result.source}, rows={len(result.data)}"


def _finnhub_check() -> str:
    if not os.getenv("FINNHUB_API_KEY"):
        return "SKIP: FINNHUB_API_KEY is not configured"
    from src.market_data import get_stock_news_with_status

    result = get_stock_news_with_status("AAPL", 1)
    status = str(result.get("source_status") or "")
    if status in {"failed", "invalid_auth"}:
        raise RuntimeError(str(result.get("error_reason") or status))
    return f"status={status}, items={len(result.get('items') or [])}"


def _marketdata_options_check() -> str:
    if not os.getenv("MARKETDATA_TOKEN"):
        return "SKIP: MARKETDATA_TOKEN is not configured"
    from src.marketdata_option_provider import fetch_marketdata_option_chain

    result = fetch_marketdata_option_chain("SPY", allow_stale=False, force_refresh=True)
    if result is None:
        raise RuntimeError("MarketData.app SPY 0DTE option chain is empty")
    return (
        f"source={result.source}, calls={len(result.calls)}, puts={len(result.puts)}, "
        f"as_of={result.data_as_of or 'unknown'}, credits={result.credits_consumed}"
    )


def _public_readonly_check() -> str:
    from src.app_mode import require_writes_enabled

    previous = os.environ.get("APP_MODE")
    os.environ["APP_MODE"] = "public_readonly"
    try:
        try:
            require_writes_enabled()
        except PermissionError:
            return "personal-data writes blocked"
        raise RuntimeError("write guard did not block public_readonly mode")
    finally:
        if previous is None:
            os.environ.pop("APP_MODE", None)
        else:
            os.environ["APP_MODE"] = previous


def _supabase_check() -> str:
    if not os.getenv("SUPABASE_URL") or not any(
        os.getenv(name)
        for name in ("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY")
    ):
        return "SKIP: Supabase credentials are not configured"
    from src.supabase_client import get_supabase_client

    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase client initialization failed")
    key = f"live_smoke_{uuid.uuid4().hex}"
    client.table("user_settings").upsert({"key": key, "value": "ok"}).execute()
    rows = client.table("user_settings").select("key,value").eq("key", key).execute()
    client.table("user_settings").delete().eq("key", key).execute()
    if not rows.data or rows.data[0].get("value") != "ok":
        raise RuntimeError("Supabase CRUD round-trip mismatch")
    return "user_settings insert/select/delete succeeded"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-optional",
        action="store_true",
        help="Treat unconfigured Supabase as a failure.",
    )
    args = parser.parse_args()
    checks = [
        _run("external_market", _external_market_check),
        _run("fred", _fred_check),
        _run("finnhub", _finnhub_check),
        _run("marketdata_options", _marketdata_options_check),
        _run("public_readonly", _public_readonly_check),
        _run("supabase", _supabase_check),
    ]
    for check in checks:
        print(f"{check.status} {check.name}: {check.detail}")
    failed = [check for check in checks if check.status == "FAIL"]
    if args.require_optional:
        failed.extend(check for check in checks if check.status == "SKIP")
    print({"checks": [asdict(check) for check in checks]})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
