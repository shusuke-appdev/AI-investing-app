"""Live integration smoke checks with cleanup and explicit skip boundaries."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def _market_forecast_check(*, required: bool) -> str:
    if not required:
        return (
            "SKIP: pass --require-market-forecast to run the model and composite smoke"
        )
    from src.services.market_composite_sentiment import (
        build_market_composite_sentiment,
    )
    from src.services.market_short_horizon_forecast import (
        build_market_short_horizon_forecast,
    )

    forecast = build_market_short_horizon_forecast(force_refresh=True)
    failures = []
    summaries = []
    for ticker in ("SPY", "QQQ"):
        target = (forecast.get("targets") or {}).get(ticker) or {}
        for horizon in ("1d", "5d", "20d"):
            item = (target.get("horizons") or {}).get(horizon) or {}
            if item.get("status") not in {"validated", "research_only"}:
                failures.append(f"{ticker}:{horizon}:status={item.get('status')}")
                continue
            if item.get("probability_up") is None or not item.get("oos_metrics"):
                failures.append(f"{ticker}:{horizon}:missing_probability_or_oos")
                continue
            summaries.append(
                f"{ticker}:{horizon}:{item.get('status')}:p_up={float(item['probability_up']):.1%}"
            )
    composite = build_market_composite_sentiment(refresh_occ=True)
    for ticker in ("SPY", "QQQ"):
        item = (composite.get("targets") or {}).get(ticker) or {}
        if item.get("status") not in {"confirmed", "partial"}:
            failures.append(f"{ticker}:composite_status={item.get('status')}")
        summaries.append(
            f"{ticker}:composite={item.get('state', 'unavailable')}/{item.get('status', 'unavailable')}"
        )
    if failures:
        raise RuntimeError("; ".join(failures))
    return "; ".join(summaries)


def _finnhub_check() -> str:
    if not os.getenv("FINNHUB_API_KEY"):
        return "SKIP: FINNHUB_API_KEY is not configured"
    from src.market_data import get_stock_news_with_status

    result = get_stock_news_with_status("AAPL", 1)
    status = str(result.get("source_status") or "")
    if status in {"failed", "invalid_auth"}:
        raise RuntimeError(str(result.get("error_reason") or status))
    return f"status={status}, items={len(result.get('items') or [])}"


def _edinet_check() -> str:
    if not os.getenv("EDINET_API_KEY"):
        return "SKIP: EDINET_API_KEY is not configured"
    from src.edinet_client import get_company_finance, is_configured

    if not is_configured():
        raise RuntimeError(
            "EDINET client is unavailable despite configured credentials"
        )
    result = get_company_finance("7203.T", limit=1)
    if not result:
        raise RuntimeError("EDINET returned no company payload for 7203.T")
    return (
        f"company={result.get('company_name') or 'unknown'}, "
        f"financials={len(result.get('financials') or [])}"
    )


def _yfinance_options_check(*, required: bool) -> str:
    if not required:
        return "SKIP: pass --require-yfinance-options to run the option-chain smoke"
    from src.option_data_provider import get_option_chain

    result = get_option_chain("SPY", allow_marketdata=False)
    if result is None:
        raise RuntimeError("SPY yfinance option chain is unavailable")
    calls, puts = result
    if calls.empty or puts.empty:
        raise RuntimeError("SPY yfinance option chain has empty calls or puts")
    return f"SPY calls={len(calls)}, puts={len(puts)}"


def _marketdata_options_check(
    *,
    tickers: list[str] | None = None,
    min_dte: int = 1,
    horizon_dtes: list[int] | None = None,
) -> str:
    mode = os.getenv("MARKETDATA_OPTIONS_MODE", "<unset>") or "<unset>"
    if not os.getenv("MARKETDATA_TOKEN"):
        return f"SKIP: MARKETDATA_TOKEN is not configured; mode={mode}"

    from src.marketdata_option_provider import (
        DEFAULT_STRIKE_LIMIT,
        SMOKE_EXPIRATION_POLICY,
        fetch_marketdata_option_chain,
    )
    from src.option_analyst import analyze_option_sentiment

    targets = tickers or ["SPY", "QQQ", "IWM"]
    summaries = []
    failures = []
    horizons = horizon_dtes or [7, 30]
    for ticker in targets:
        result = fetch_marketdata_option_chain(
            ticker,
            min_dte=min_dte,
            expiration_policy=SMOKE_EXPIRATION_POLICY,
            strike_limit=DEFAULT_STRIKE_LIMIT,
            allow_stale=False,
            force_refresh=True,
        )
        if result is None or result.calls.empty or result.puts.empty:
            failures.append(f"{ticker}:no_rows")
            continue
        calls = len(result.calls)
        puts = len(result.puts)
        cap_note = (
            "side_cap_reached=true"
            if calls >= DEFAULT_STRIKE_LIMIT or puts >= DEFAULT_STRIKE_LIMIT
            else "side_cap_reached=false"
        )
        summaries.append(
            f"{ticker}:expiration={result.resolved_expiration or 'unknown'} "
            f"dte={result.resolved_dte} calls={calls}/{DEFAULT_STRIKE_LIMIT} "
            f"puts={puts}/{DEFAULT_STRIKE_LIMIT} {cap_note} "
            f"as_of={result.data_as_of or 'unknown'} "
            f"credits={result.credits_consumed}/{result.credits_remaining}"
        )
        for target_dte in horizons:
            horizon = fetch_marketdata_option_chain(
                ticker,
                target_dte=target_dte,
                min_dte=min_dte,
                expiration_policy=SMOKE_EXPIRATION_POLICY,
                strike_limit=DEFAULT_STRIKE_LIMIT,
                allow_stale=False,
                force_refresh=True,
            )
            if horizon is None or horizon.calls.empty or horizon.puts.empty:
                failures.append(f"{ticker}:target_dte={target_dte}:no_rows")
                continue
            summaries.append(
                f"{ticker}:target_dte={target_dte} "
                f"expiration={horizon.resolved_expiration or 'unknown'} "
                f"dte={horizon.resolved_dte} "
                f"calls={len(horizon.calls)}/{DEFAULT_STRIKE_LIMIT} "
                f"puts={len(horizon.puts)}/{DEFAULT_STRIKE_LIMIT}"
            )
        analysis = analyze_option_sentiment(ticker, allow_marketdata=True)
        term_horizons = list(analysis.get("horizons") or [])
        by_key = {str(item.get("key")): item for item in term_horizons}
        missing_terms = [
            key for key in ("current", "one_week", "one_month") if key not in by_key
        ]
        inactive_terms = [
            key
            for key, item in by_key.items()
            if key in {"current", "one_week", "one_month"}
            and not bool(item.get("provider_active"))
        ]
        non_marketdata_terms = [
            key
            for key, item in by_key.items()
            if key in {"current", "one_week", "one_month"}
            and "marketdata.app" not in str(item.get("source") or "")
        ]
        if missing_terms:
            failures.append(
                f"{ticker}:term_structure_missing={','.join(missing_terms)}"
            )
        if inactive_terms:
            failures.append(
                f"{ticker}:term_structure_inactive={','.join(inactive_terms)}"
            )
        if non_marketdata_terms:
            failures.append(
                f"{ticker}:term_structure_non_marketdata="
                + ",".join(non_marketdata_terms)
            )
        if not missing_terms and not inactive_terms and not non_marketdata_terms:
            summaries.append(
                f"{ticker}:term_structure="
                f"{analysis.get('term_structure', {}).get('summary') or 'available'}"
            )
            summaries.append(
                f"{ticker}:term_horizons="
                + ",".join(_term_horizon_detail(item) for item in term_horizons)
            )

    detail = f"mode={mode}; min_dte={min_dte}; " + "; ".join(summaries)
    if failures and not summaries:
        raise RuntimeError("MarketData.app option chains empty: " + "; ".join(failures))
    if failures:
        return "DEGRADED: " + detail + "; failures=" + ", ".join(failures)
    return detail


def _term_horizon_detail(item: dict[str, Any]) -> str:
    key = str(item.get("key") or "unknown")
    expiration = str(item.get("resolved_expiration") or "unknown")
    dte = item.get("resolved_dte")
    iv = item.get("iv")
    as_of = str(item.get("data_as_of") or "unknown")
    source = str(item.get("source") or "unknown")
    try:
        iv_text = f"{float(iv):.1%}"
    except (TypeError, ValueError):
        iv_text = "unknown"
    return f"{key}@{expiration}/dte={dte}/iv={iv_text}/as_of={as_of}/source={source}"


def _latest_updated_timestamp(values: Any) -> str:
    if values is None:
        return ""
    try:
        numeric = values.dropna()
    except AttributeError:
        return ""
    if numeric.empty:
        return ""
    value = float(numeric.max())
    if value > 10_000_000_000:
        value = value / 1000.0
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _deployment_guard_check() -> str:
    from src.deployment_guard import require_safe_deployment

    previous_space = os.environ.get("SPACE_ID")
    previous_ack = os.environ.get("PRIVATE_DEPLOYMENT_ACK")
    try:
        os.environ.pop("SPACE_ID", None)
        os.environ.pop("PRIVATE_DEPLOYMENT_ACK", None)
        require_safe_deployment()
        os.environ["SPACE_ID"] = "live-smoke/hosted"
        try:
            require_safe_deployment()
        except RuntimeError:
            os.environ["PRIVATE_DEPLOYMENT_ACK"] = "1"
            require_safe_deployment()
            return "local allowed; hosted requires access-control acknowledgement"
        raise RuntimeError("hosted deployment guard did not fail closed")
    finally:
        if previous_space is None:
            os.environ.pop("SPACE_ID", None)
        else:
            os.environ["SPACE_ID"] = previous_space
        if previous_ack is None:
            os.environ.pop("PRIVATE_DEPLOYMENT_ACK", None)
        else:
            os.environ["PRIVATE_DEPLOYMENT_ACK"] = previous_ack


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


def _required_check_names(args: argparse.Namespace) -> set[str]:
    """Return only the checks explicitly required by CLI flags."""

    required: set[str] = set()
    if args.require_optional or args.require_supabase:
        required.add("supabase")
    if args.require_finnhub:
        required.add("finnhub")
    if args.require_edinet:
        required.add("edinet")
    if args.require_marketdata:
        required.add("marketdata_options")
    if args.require_market_forecast:
        required.add("market_forecast")
    if args.require_yfinance_options:
        required.add("yfinance_options")
    return required


def _failed_checks(checks: list[Check], required_names: set[str]) -> list[Check]:
    """Return hard failures and explicitly required non-pass checks once each."""

    failures = {
        check.name: check
        for check in checks
        if check.status == "FAIL"
        or (check.name in required_names and check.status != "PASS")
    }
    return list(failures.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-optional",
        action="store_true",
        help="Compatibility alias for --require-supabase.",
    )
    parser.add_argument(
        "--require-supabase",
        action="store_true",
        help="Require the Supabase user_settings CRUD smoke.",
    )
    parser.add_argument(
        "--require-finnhub",
        action="store_true",
        help="Require the configured Finnhub news smoke.",
    )
    parser.add_argument(
        "--require-edinet",
        action="store_true",
        help="Require the configured EDINET company-finance smoke.",
    )
    parser.add_argument(
        "--require-yfinance-options",
        action="store_true",
        help="Run and require a live SPY yfinance option chain.",
    )
    parser.add_argument(
        "--require-marketdata",
        action="store_true",
        help="Treat MarketData.app options skip/degraded as a failure.",
    )
    parser.add_argument(
        "--require-market-forecast",
        action="store_true",
        help="Run and require the short-horizon forecast and composite sentiment smoke.",
    )
    parser.add_argument(
        "--marketdata-tickers",
        default="SPY,QQQ,IWM",
        help="Comma-separated tickers for the MarketData.app live option smoke.",
    )
    parser.add_argument(
        "--marketdata-min-dte",
        type=int,
        default=1,
        help="Minimum DTE for MarketData.app smoke. Defaults to 1 to avoid 0DTE timing failures.",
    )
    parser.add_argument(
        "--marketdata-horizon-dtes",
        default="7,30",
        help="Comma-separated target DTEs for MarketData.app horizon smoke.",
    )
    args = parser.parse_args()
    marketdata_tickers = [
        item.strip().upper()
        for item in args.marketdata_tickers.split(",")
        if item.strip()
    ]
    marketdata_horizon_dtes = [
        int(item.strip())
        for item in args.marketdata_horizon_dtes.split(",")
        if item.strip()
    ]
    checks = [
        _run("external_market", _external_market_check),
        _run("fred", _fred_check),
        _run(
            "market_forecast",
            lambda: _market_forecast_check(required=args.require_market_forecast),
        ),
        _run("finnhub", _finnhub_check),
        _run("edinet", _edinet_check),
        _run(
            "yfinance_options",
            lambda: _yfinance_options_check(required=args.require_yfinance_options),
        ),
        _run(
            "marketdata_options",
            lambda: _marketdata_options_check(
                tickers=marketdata_tickers,
                min_dte=max(0, args.marketdata_min_dte),
                horizon_dtes=marketdata_horizon_dtes,
            ),
        ),
        _run("deployment_guard", _deployment_guard_check),
        _run("supabase", _supabase_check),
    ]
    for check in checks:
        print(f"{check.status} {check.name}: {check.detail}")
    failed = _failed_checks(checks, _required_check_names(args))
    print({"checks": [asdict(check) for check in checks]})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
