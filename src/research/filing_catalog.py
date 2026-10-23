"""Free primary-filing discovery; metadata is never marked document-reviewed."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

import requests


def issuer_links(ticker: str, info: dict) -> dict:
    links = (
        [
            {
                "title": "EDINET公式開示検索",
                "url": "https://disclosure2.edinet-fsa.go.jp/",
            }
        ]
        if ticker.endswith(".T")
        else [{"title": "SEC公式企業検索", "url": "https://www.sec.gov/search-filings"}]
    )
    website = str(info.get("website") or "")
    parsed = urlsplit(website)
    if (
        parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
    ):
        links.append({"title": "会社公式サイト（IR資料を確認）", "url": website})
    return {
        "status": "unreviewed",
        "links": links,
        "requested_coverage": "3 consecutive annual filings + latest interim; segment notes and issuer IR",
        "warning": "リンクだけでは資料内容・期間の確認になりません。開いた資料をevidenceに記録してください。",
    }


def select_filings(columns: dict, cik: str) -> dict:
    rows = []
    for i, form in enumerate(columns.get("form", [])):
        if form not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "10-Q", "10-Q/A"}:
            continue
        row = {
            key: values[i]
            for key, values in columns.items()
            if isinstance(values, list) and i < len(values)
        }
        accession, document = (
            row.get("accessionNumber", ""),
            row.get("primaryDocument", ""),
        )
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or not re.fullmatch(
            r"[A-Za-z0-9_.-]+", document
        ):
            continue
        try:
            period_end = date.fromisoformat(row.get("reportDate", ""))
            published = date.fromisoformat(row.get("filingDate", ""))
        except (TypeError, ValueError):
            continue
        if not period_end <= published <= date.today():
            continue
        rows.append(
            {
                "form": form,
                "period_end": row["reportDate"],
                "published_on": row["filingDate"],
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}",
                "review": "unverified",
            }
        )
    rows.sort(key=lambda row: (row["period_end"], row["published_on"]), reverse=True)
    annual, interim = {}, {}
    for row in rows:
        (interim if row["form"].startswith("10-Q") else annual).setdefault(
            row["period_end"], row
        )
    selected = list(annual.values())[:3]
    latest = next(
        (
            row
            for row in interim.values()
            if not selected or row["period_end"] > selected[0]["period_end"]
        ),
        None,
    )
    return {
        "annual": selected,
        "latest_interim": latest,
        "status": "unreviewed",
        "coverage": "catalog_complete" if len(selected) == 3 and latest else "partial",
        "warning": "提出履歴の資料候補。セグメント・改訂内容は別途確認。20-F企業の中間は会社IR／6-Kで確認。",
    }


def fetch_sec_catalog(ticker: str, cik: str, user_agent: str) -> dict:
    if not re.fullmatch(r"\d{1,10}", cik):
        raise ValueError("CIK must contain 1 to 10 digits")
    if (
        not user_agent
        or "@" not in user_agent
        or "\n" in user_agent
        or "\r" in user_agent
    ):
        return {
            "status": "unavailable",
            "reason": "SEC_USER_AGENTに実際の連絡先を含む識別情報が必要。CodexのWebでSEC／会社IRを確認する代替も利用できます。",
        }
    normalized = cik.zfill(10)
    headers = {"User-Agent": user_agent, "Accept": "application/json"}

    def get(name):
        response = requests.get(
            f"https://data.sec.gov/submissions/{name}",
            headers=headers,
            timeout=15,
            allow_redirects=False,
        )
        response.raise_for_status()
        if response.status_code != 200:
            raise requests.RequestException("Unexpected SEC response")
        return response.json()

    try:
        root = get(f"CIK{normalized}.json")
        if ticker not in [value.upper() for value in root.get("tickers", [])]:
            raise ValueError("Ticker and SEC issuer CIK mismatch")
        columns = root.get("filings", {}).get("recent", {})
        catalog = select_filings(columns, normalized)
        if len(catalog["annual"]) < 3:
            for archive in root.get("filings", {}).get("files", [])[:2]:
                name = archive.get("name", "")
                if not re.fullmatch(r"CIK\d{10}-submissions-\d{3}\.json", name):
                    continue
                extra = get(name)
                columns = {
                    key: values + extra.get(key, [])
                    for key, values in columns.items()
                    if isinstance(values, list)
                }
                catalog = select_filings(columns, normalized)
                if len(catalog["annual"]) == 3:
                    break
        return {
            **catalog,
            "cik": normalized,
            "issuer": root.get("name", ""),
            "ticker": ticker,
            "source": "SEC submissions API",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_url": f"https://data.sec.gov/submissions/CIK{normalized}.json",
        }
    except requests.RequestException as exc:
        return {
            "status": "unavailable",
            "error_type": type(exc).__name__,
            "reason": "SEC取得失敗。Web／会社IRで原資料を確認してください。",
        }
