"""Bounded official inputs, with explicit availability instead of guessed values."""

from __future__ import annotations

import csv
import hashlib
import math
import re
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.persistent_cache import repo_state_cache, utc_now_iso

MOF = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"
MOF_HISTORY = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
FED = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BOJ = "https://www.boj.or.jp/mopo/mpmsche_minu/index.htm"
JPX = "https://www.jpx.co.jp/markets/statistics-equities/investor-type/index.html"


def official_document(url: str, *, encoding: str = "utf-8") -> dict:
    cache = repo_state_cache("standard_official")
    key = hashlib.sha256(url.encode()).hexdigest()
    cached = cache.read(key, fresh_seconds=12 * 3600, stale_seconds=7 * 86400)
    if cached.status == "fresh":
        return {
            **cached.payload,
            "fetched_at": cached.fetched_at,
            "cache_status": "persistent_cache",
            "is_stale": False,
        }
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        if len(response.content) > 5 * 1024 * 1024:
            raise ValueError("Official document too large")
        payload = {
            "text": response.content.decode(encoding),
            "source": url,
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "status": "available",
        }
        cache.write(key, payload)
        return {
            **payload,
            "fetched_at": utc_now_iso(),
            "cache_status": "live",
            "is_stale": False,
        }
    except (requests.RequestException, ValueError, UnicodeError) as exc:
        # Exception URLs/headers are not persisted.
        return {
            **(cached.payload if cached.is_available else {}),
            "source": url,
            "fetched_at": cached.fetched_at,
            "cache_status": "stale_cache" if cached.is_available else "failed",
            "is_stale": cached.is_available,
            "status": "stale" if cached.is_available else "unavailable",
            "reason": f"公式資料の取得失敗 ({type(exc).__name__})。予定・値を推測しません。",
        }


def parse_mof(text: str) -> list[dict]:
    lines = list(csv.reader(StringIO(text.replace("\r\r\n", "\n"))))
    if not lines or not any("単位" in cell and "%" in cell for cell in lines[0]):
        raise ValueError("Unconfirmed MOF unit")
    header = next((row for row in lines if row and row[0] == "基準日"), [])
    if "10年" not in header:
        raise ValueError("Unknown MOF columns")
    column = header.index("10年")
    rows = []
    for row in lines:
        match = re.fullmatch(r"([RHS])(\d+)\.(\d+)\.(\d+)", row[0]) if row else None
        if not match or len(row) <= column or row[column] in {"", "-"}:
            continue
        era, year, month, day = match.groups()
        observed = date(
            {"R": 2018, "H": 1988, "S": 1925}[era] + int(year), int(month), int(day)
        )
        value = float(row[column])
        if not -5 <= value <= 30:
            raise ValueError("Invalid MOF rate")
        rows.append({"date": observed.isoformat(), "value": value})
    if len({r["date"] for r in rows}) != len(rows):
        raise ValueError("Duplicate MOF date")
    return sorted(rows, key=lambda r: r["date"])


def event_row(
    label: str,
    day: date,
    source: str,
    *,
    local_time: str | None = None,
    zone: str | None = None,
) -> dict:
    when = (
        datetime.fromisoformat(f"{day}T{local_time}").replace(tzinfo=ZoneInfo(zone))
        if local_time and zone
        else None
    )
    return {
        "label": label,
        "date": day.isoformat(),
        "source": source,
        "time_status": "confirmed" if when else "time_unknown",
        "local_time": when.isoformat() if when else None,
        "utc_time": when.astimezone(timezone.utc).isoformat() if when else None,
        "timezone": zone,
        "status": "scheduled",
        "warning": "公式予定。変更の可能性があり、更新時に再確認。",
    }


def parse_events(text: str, provider: str, year: int) -> list[dict]:
    soup = BeautifulSoup(text, "html.parser")
    rows = []
    if provider == "Fed":
        months = {datetime(2000, m, 1).strftime("%B"): m for m in range(1, 13)}
        for panel in soup.select(".panel"):
            heading = panel.select_one(".panel-heading")
            if not heading or f"{year} FOMC Meetings" not in heading.get_text():
                continue
            for meeting in panel.select(".fomc-meeting"):
                month, days = (
                    meeting.select_one(".fomc-meeting__month"),
                    meeting.select_one(".fomc-meeting__date"),
                )
                if not month or not days:
                    continue
                m = months.get(month.get_text(strip=True))
                numbers = re.findall(r"\d+", days.get_text())
                if m and numbers:
                    # Calendar lists meetings, not a guaranteed statement time.
                    rows.append(
                        event_row(
                            "FOMC 政策会合最終日", date(year, m, int(numbers[-1])), FED
                        )
                    )
    elif provider == "BOJ":
        for table in soup.select("table"):
            caption = table.find("caption")
            if not caption or str(year) not in caption.get_text():
                continue
            for tr in table.select("tbody tr"):
                cells = tr.find_all("td")
                if not cells:
                    continue
                text_date = cells[0].get_text(" ", strip=True)
                month = re.search(r"(\d+)月", text_date)
                days = re.findall(r"(\d+)日", text_date)
                if month and days:
                    rows.append(
                        event_row(
                            "日銀 政策会合最終日",
                            date(year, int(month[1]), int(days[-1])),
                            BOJ,
                        )
                    )
    elif provider == "BLS":
        for tr in soup.select("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
            if len(cells) < 3:
                continue
            match = re.search(r"([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})", cells[0])
            clock = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", cells[1], re.I)
            if not match or not any(
                word in " ".join(cells[2:])
                for word in ("Consumer Price", "Employment Situation", "Producer Price")
            ):
                continue
            day = datetime.strptime(" ".join(match.groups()), "%B %d %Y").date()
            time = (
                f"{int(clock[1]) % 12 + (12 if clock[3].upper() == 'PM' else 0):02}:{clock[2]}"
                if clock
                else None
            )
            rows.append(
                event_row(
                    " / ".join(cells[2:]),
                    day,
                    f"https://www.bls.gov/schedule/{year}/home.htm",
                    local_time=time,
                    zone="America/New_York",
                )
            )
    return rows


def official_inputs(today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    mof = official_document(MOF, encoding="cp932")
    try:
        mof["points"] = parse_mof(mof.get("text", ""))
    except (ValueError, IndexError):
        mof.update(
            points=[], status="unavailable", reason="金利形式・単位を確認できません。"
        )
    mof.pop("text", None)
    archive = official_document(MOF_HISTORY, encoding="cp932")
    try:
        historical = parse_mof(archive.get("text", ""))
        by_date = {r["date"]: r for r in historical}
        by_date.update({r["date"]: r for r in mof["points"]})
        mof["points"] = sorted(by_date.values(), key=lambda r: r["date"])
        mof["history_source"] = MOF_HISTORY
        mof["history_fetched_at"] = archive.get("fetched_at")
        mof["history_cache_status"] = archive.get("cache_status")
        mof["is_stale"] = bool(mof.get("is_stale") or archive.get("is_stale"))
        mof["revision_policy"] = (
            "同日重複は当月公表値を優先。過去値と当月値の出典を別記。"
        )
    except (ValueError, IndexError):
        mof["history_reason"] = (
            "過去金利の形式・単位を確認できません。履歴が必要な変化は未確認。"
        )
    events, states = [], []
    for provider, url in [
        ("Fed", FED),
        ("BOJ", BOJ),
        ("BLS", f"https://www.bls.gov/schedule/{today.year}/home.htm"),
    ]:
        document = official_document(url)
        try:
            parsed = parse_events(document.get("text", ""), provider, today.year)
            parsed += parse_events(document.get("text", ""), provider, today.year + 1)
        except (ValueError, IndexError):
            parsed = []
        if not parsed:
            document.update(
                status="unavailable",
                reason=document.get("reason") or "公式予定の形式を確認できません。",
            )
        future = sorted(
            (r for r in parsed if r["date"] >= today.isoformat()),
            key=lambda r: r["date"],
        )
        selected = [
            r for r in future if r["date"] <= (today + timedelta(days=14)).isoformat()
        ]
        if provider != "BLS" and future and future[0] not in selected:
            selected.append({**future[0], "next_policy_meeting": True})
        events.extend(
            {
                **r,
                "fetched_at": document.get("fetched_at"),
                "cache_status": document.get("cache_status"),
                "is_stale": document.get("is_stale"),
            }
            for r in selected
        )
        document.pop("text", None)
        states.append({"provider": provider, **document})
    return {
        "mof": mof,
        "events": sorted(events, key=lambda r: r["date"]),
        "event_sources": states,
        "jpx": {
            "status": "unavailable",
            "source": JPX,
            "terms": "https://www.jpx.co.jp/term-of-use/index.html",
            "reason": "無許諾の二次利用・再配信が禁止。自動収集しません。許諾を確認した入力のみ使用。先物・貸借は合算しません。",
        },
    }


def reviewed_flow(rows: list[dict]) -> dict:
    """Explicit permission-attested amounts only. Never fetch the restricted site."""
    checked = []
    for row in rows:
        if (
            row.get("permission_confirmed") is not True
            or row.get("opened_and_checked") is not True
        ):
            raise ValueError("JPX permission and source check required")
        if (
            urlparse(row.get("source", "")).hostname != "www.jpx.co.jp"
            or row.get("scope") != "cash_equity_foreigners"
            or row.get("unit") != "JPY"
        ):
            raise ValueError("Unconfirmed JPX scope/unit/source")
        start, end = (
            date.fromisoformat(row["period_start"]),
            date.fromisoformat(row["period_end"]),
        )
        value = row.get("net_amount")
        if (
            start > end
            or (end - start).days > 6
            or not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise ValueError("Invalid weekly flow")
        if (
            not row.get("locator")
            or not row.get("checked_on")
            or not row.get("permission_basis")
        ):
            raise ValueError("Missing JPX check record")
        confirmed = date.fromisoformat(row["checked_on"])
        if confirmed < end or confirmed > datetime.now(timezone.utc).date():
            raise ValueError("Invalid JPX confirmation date")
        checked.append(row)
    checked.sort(key=lambda r: r["period_start"], reverse=True)
    if any(
        b["period_end"] >= a["period_start"]
        for a, b in zip(checked, checked[1:], strict=False)
    ):
        raise ValueError("Overlapping JPX weeks")
    anchors = [
        date.fromisoformat(r["period_start"])
        - timedelta(days=date.fromisoformat(r["period_start"]).weekday())
        for r in checked[:4]
    ]
    consecutive = len(anchors) == 4 and all(
        (a - b).days == 7 for a, b in zip(anchors, anchors[1:], strict=False)
    )
    stale = bool(
        checked
        and (
            datetime.now(timezone.utc).date()
            - date.fromisoformat(checked[0]["period_end"])
        ).days
        > 14
    )
    return {
        "status": "stale" if stale else "available" if checked else "unavailable",
        "is_stale": stale,
        "observed_on": checked[0]["period_end"] if checked else None,
        "weeks": checked,
        "current_week": checked[0] if checked else None,
        "four_week_net": sum(r["net_amount"] for r in checked[:4])
        if consecutive
        else None,
        "four_week_reason": "非重複・連続4週"
        if consecutive
        else "非重複の連続4週を確認できません。欠けた週を0にしません。",
        "four_week_sources": checked[:4],
        "unit": "JPY",
        "source": JPX,
        "reason": "許諾・原資料確認済みの入力。資料の確認日は更新処理で変更しません。"
        if checked
        else "確認済み入力なし",
    }


def validate_market_inputs(value: dict) -> dict:
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "jpx_weeks"}
        or value["version"] != "reviewed-market-input-v1"
    ):
        raise ValueError("Invalid reviewed market input")
    if (
        not isinstance(value["jpx_weeks"], list)
        or len(value["jpx_weeks"]) > 52
        or any(not isinstance(r, dict) for r in value["jpx_weeks"])
    ):
        raise ValueError("Invalid reviewed JPX weeks")
    return {"jpx": reviewed_flow(value["jpx_weeks"])}
