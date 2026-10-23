"""Bounded free financial acquisition with per-issuer checkpoints and no model."""

from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from time import sleep

import requests

from src.persistent_cache import utc_now_iso
from src.research.quarterly import Quarter, evaluate_quarters
from src.storage.atomic_json import read_json, write_json

ROOT = Path(__file__).resolve().parents[2]


def sec_json(url: str, user_agent: str) -> dict:
    if "@" not in user_agent or "\n" in user_agent or "\r" in user_agent:
        raise ValueError("SEC identifying contact is unavailable")
    sleep(0.2)
    response = requests.get(
        url,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
        timeout=12,
    )
    response.raise_for_status()
    if len(response.content) > 25 * 1024 * 1024:
        raise ValueError("SEC response too large")
    return response.json()


def sec_quarters(ticker: str, data: dict, fetched: str) -> list[dict]:
    """Only original standalone quarters; never subtract cumulative EPS."""
    tags = {
        "revenue": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            "Revenues",
        ],
        "diluted_eps": ["EarningsPerShareDiluted"],
        "parent_net_income": [
            "NetIncomeLossAvailableToCommonStockholdersBasic",
            "NetIncomeLoss",
        ],
    }
    grouped = {}
    for metric, candidates in tags.items():
        for tag in candidates:
            for unit, rows in (
                data.get("facts", {})
                .get("us-gaap", {})
                .get(tag, {})
                .get("units", {})
                .items()
            ):
                if (metric == "diluted_eps" and unit != "USD/shares") or (
                    metric != "diluted_eps" and unit != "USD"
                ):
                    continue
                for row in rows:
                    try:
                        start, end = (
                            date.fromisoformat(row["start"]),
                            date.fromisoformat(row["end"]),
                        )
                        if not 65 <= (end - start).days <= 110 or row.get(
                            "form"
                        ) not in {"10-Q", "10-Q/A", "10-K", "10-K/A"}:
                            continue
                        key = (start.isoformat(), end.isoformat(), row["accn"])
                        record = grouped.setdefault(
                            key,
                            {
                                "period_start": key[0],
                                "period_end": key[1],
                                "accession": key[2],
                                "published_on": row["filed"],
                            },
                        )
                        if metric == "parent_net_income" and metric not in record:
                            record["ownership_basis"] = (
                                "parent_common"
                                if tag
                                == "NetIncomeLossAvailableToCommonStockholdersBasic"
                                else "parent"
                            )
                        record.setdefault(metric, row["val"])
                    except (KeyError, ValueError, TypeError):
                        continue
    selected = {}
    for record in grouped.values():
        if not all(k in record for k in tags):
            continue
        key = record["period_end"]
        if (
            key not in selected
            or record["published_on"] > selected[key]["published_on"]
        ):
            selected[key] = record
    # EPS restatements/splits cannot be inferred by inspecting price ratios.
    # Require all quarters to occur together in one filing to share an EPS basis;
    # otherwise label each filing's basis, causing a reasoned incomparable state.
    return [
        Quarter(
            ticker=ticker,
            currency="USD",
            accounting_basis="US_GAAP",
            consolidation="consolidated",
            split_basis="SEC original filing " + r["accession"],
            source="https://www.sec.gov/Archives/edgar/data/"
            + str(int(data["cik"]))
            + "/"
            + r["accession"].replace("-", "")
            + "/",
            fetched_at=fetched,
            **r,
        ).model_dump(mode="json")
        for r in sorted(selected.values(), key=lambda r: r["period_end"])[-10:]
    ]


def yahoo_quarters(ticker: str, fetched: str) -> tuple[list[dict], str]:
    import yfinance as yf

    obj = yf.Ticker(ticker)
    income = obj.get_income_stmt(freq="quarterly")
    if income is None or income.empty:
        return [], "general"
    info = obj.get_info()
    profile = (
        "unsupported"
        if info.get("quoteType") not in {"EQUITY", None}
        else "reit"
        if "reit" in str(info.get("industry", "")).lower()
        else "financial"
        if info.get("sector") == "Financial Services"
        else "general"
    )
    currency = info.get("financialCurrency") or info.get("currency")
    if not currency:
        return [], profile
    columns = sorted(income.columns)

    def value(name, column):
        from src.research.topdown import num

        return num(income.at[name, column]) if name in income.index else None

    rows = []
    for i, column in enumerate(columns):
        end = column.date()
        start = columns[i - 1].date() + timedelta(days=1) if i else None
        # The provider's quarterly table is unreviewed; preserve this uncertainty.
        record = Quarter(
            ticker=ticker,
            period_end=end,
            period_start=start,
            currency=currency,
            revenue=value("TotalRevenue", column),
            diluted_eps=value("DilutedEPS", column),
            parent_net_income=value("NetIncomeCommonStockholders", column),
            accounting_basis="provider_reported_unreviewed",
            ownership_basis="parent_common"
            if "NetIncomeCommonStockholders" in income.index
            else "unconfirmed",
            consolidation="consolidated",
            split_basis="provider_current_quarterly_table_unreviewed",
            source=f"https://finance.yahoo.com/quote/{ticker}/financials/",
            fetched_at=fetched,
            derivation="単独四半期表。開始日は前の報告四半期末+1日（最古は不明）。希薄化EPS・分割調整は原資料未照合。",
        )
        rows.append(record.model_dump(mode="json"))
    return rows, profile


def acquire(ticker: str, profile: str, cik: str | None = None) -> dict:
    fetched, attempts, records = utc_now_iso(), [], []
    if cik and not ticker.endswith(".T"):
        try:
            records = sec_quarters(
                ticker,
                sec_json(
                    f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json",
                    os.environ.get("SEC_USER_AGENT", ""),
                ),
                fetched,
            )
            attempts.append(
                {
                    "provider": "SEC",
                    "status": "available" if records else "insufficient_data",
                }
            )
        except (requests.RequestException, ValueError, KeyError, TypeError):
            attempts.append({"provider": "SEC", "status": "unavailable"})
    evaluated = evaluate_quarters(records, profile)
    if evaluated["status"] != "available":
        try:
            fallback, provider_profile = yahoo_quarters(ticker, fetched)
            attempts.append(
                {
                    "provider": "Yahoo",
                    "status": "available" if fallback else "insufficient_data",
                }
            )
            if fallback:
                records, profile = (
                    fallback,
                    provider_profile if provider_profile != "general" else profile,
                )
                evaluated = evaluate_quarters(records, profile)
        except Exception as exc:
            attempts.append(
                {
                    "provider": "Yahoo",
                    "status": "unavailable",
                    "error_type": type(exc).__name__,
                }
            )
    return {
        **evaluated,
        "ticker": ticker,
        "fetched_at": fetched,
        "attempts": attempts,
        "status": evaluated["status"]
        if records or profile != "general"
        else "unavailable",
    }


def refresh_fundamentals(
    bundle: dict,
    markets: tuple[str, ...],
    progress=lambda _: None,
    *,
    root: Path | None = None,
) -> dict:
    """Single caller holds the cross-process update lock; completed issuers resume."""
    root = root or ROOT
    directory = root / ".states" / "quarterly_fundamentals"
    directory.mkdir(parents=True, exist_ok=True)
    tickers, ciks = {}, {}
    for market in markets:
        packet = bundle["sections"].get("markets", {}).get(market) or bundle[
            "sections"
        ].get("market", {})
        for row in packet.get("analysis", {}).get("topdown", {}).get("screening", []):
            tickers[row["ticker"]] = (row, packet)
    if any(not t.endswith(".T") for t in tickers) and "@" in os.environ.get(
        "SEC_USER_AGENT", ""
    ):
        try:
            mapping_path = directory / "sec_tickers.json"
            cached = read_json(mapping_path, {})
            if cached.get("fetched_on") != date.today().isoformat():
                cached = {
                    "fetched_on": date.today().isoformat(),
                    "data": sec_json(
                        "https://www.sec.gov/files/company_tickers.json",
                        os.environ["SEC_USER_AGENT"],
                    ),
                }
                write_json(mapping_path, cached)
            ciks = {r["ticker"]: str(r["cik_str"]) for r in cached["data"].values()}
        except (OSError, ValueError, KeyError, TypeError, requests.RequestException):
            pass
    counts = {"success": 0, "insufficient": 0, "failed": 0, "cached": 0}
    for i, (ticker, (row, packet)) in enumerate(tickers.items(), 1):
        progress(
            f"業績 {i}/{len(tickers)} {ticker} · 成功{counts['success']} 不足{counts['insufficient']} 失敗{counts['failed']}"
        )
        path = directory / (hashlib.sha256(ticker.encode()).hexdigest() + ".json")
        try:
            cached = read_json(path, {})
            stamp = datetime.fromisoformat(cached["fetched_at"])
            fresh = 0 <= (
                datetime.now(timezone.utc) - stamp
            ).total_seconds() < 7 * 86400 and cached.get("status") not in {
                "unavailable",
                "failed",
            }
        except (OSError, ValueError, KeyError, TypeError):
            cached, fresh = {}, False
        if fresh:
            result = cached
            counts["cached"] += 1
        else:
            result = acquire(ticker, row.get("profile", "general"), ciks.get(ticker))
            if result["status"] == "unavailable" and cached:
                result["previous_result"] = cached
            write_json(path, result)
        existing = (
            packet["analysis"].setdefault("quarterly_fundamentals", {}).get(ticker)
        )
        if existing:
            reviewed = (
                existing
                if existing.get("verification") == "一次資料確認済み"
                else existing.get("reviewed_previous")
            )
            if reviewed:
                result = {**result, "reviewed_previous": reviewed}
        packet["analysis"]["quarterly_fundamentals"][ticker] = result
        counts[
            "success"
            if result["status"] == "available"
            else "failed"
            if result["status"] == "unavailable"
            else "insufficient"
        ] += 1
    return {
        "counts": counts,
        "issuer_count": len(tickers),
        "status": "completed"
        if tickers and not counts["failed"] and not counts["insufficient"]
        else "partial",
        "fetched_at": utc_now_iso(),
        "reason": "取得と一次資料照合は別。再開は7日以内の取得済み銘柄を再利用。",
    }
