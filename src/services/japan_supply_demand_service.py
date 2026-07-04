"""Japanese margin and lending supply-demand diagnostics."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from src.persistent_cache import utc_now_iso
from src.stock_data_provider import normalize_ticker

DIRECT = "direct"
UNAVAILABLE = "unavailable"


def build_japan_supply_demand_context(
    ticker: str,
    price_df: pd.DataFrame | None,
    *,
    margin_rows: list[dict[str, Any]] | None = None,
    loan_alert: dict[str, Any] | None = None,
    today: str | pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Evaluate the six-month Japanese margin expiry setup for one stock."""

    normalized = normalize_ticker(ticker)
    if not normalized.endswith(".T"):
        return {
            "ticker": normalized,
            "status": "not_applicable",
            "source_type": UNAVAILABLE,
            "summary": "日本株以外は制度信用半年期日戦略の対象外。",
            "items": [],
            "quality_warnings": [],
        }

    rows = margin_rows if margin_rows is not None else _env_margin_rows(normalized)
    alert = loan_alert if loan_alert is not None else _env_loan_alert(normalized)
    price = _normalize_price_frame(price_df)
    price_setup = _price_expiry_setup(price, today=today)
    margin_setup = _margin_setup(rows)
    invalidation = _invalidation(price, rows)

    score = 0.0
    items = []
    if price_setup["available"]:
        score += 0.3 if price_setup["near_high_expiry"] else 0.0
    items.append(
        _item(
            "six_month_high_expiry",
            "高値から約6か月",
            price_setup["near_high_expiry"],
            price_setup["detail"],
            DIRECT if price_setup["available"] else UNAVAILABLE,
        )
    )
    if margin_setup["available"]:
        if margin_setup["system_margin_ratio"] is not None:
            ratio = margin_setup["system_margin_ratio"]
            score += 0.35 if ratio < 1.0 else 0.2 if ratio <= 1.05 else 0.0
        if margin_setup["buy_balance_improving"]:
            score += 0.15
    items.append(
        _item(
            "system_margin_ratio",
            "制度信用倍率",
            margin_setup["ratio_signal"],
            margin_setup["detail"],
            DIRECT if margin_setup["available"] else UNAVAILABLE,
        )
    )
    if alert.get("active"):
        score += 0.1
    items.append(
        _item(
            "loan_stock_alert",
            "貸株注意喚起/逆日歩",
            bool(alert.get("active")),
            str(alert.get("detail") or "貸株注意喚起・逆日歩データなし。"),
            DIRECT if alert else UNAVAILABLE,
        )
    )
    if invalidation["active"]:
        score = min(score, 0.25)
    items.append(
        _item(
            "sharp_drop_buy_balance_increase",
            "急落時の買い残増加による無効化",
            invalidation["active"],
            invalidation["detail"],
            DIRECT if invalidation["available"] else UNAVAILABLE,
            negative=True,
        )
    )

    available = sum(1 for item in items if item["source_type"] != UNAVAILABLE)
    status = "available" if available >= 2 else "insufficient_data"
    label = "有効候補" if score >= 0.6 else "監視" if score >= 0.35 else "根拠不足"
    if invalidation["active"]:
        label = "無効化警戒"
    warnings = []
    if not margin_setup["available"]:
        warnings.append("制度信用残高データが未取得です。")
    if not alert:
        warnings.append("貸株注意喚起・逆日歩データが未取得です。")
    return {
        "ticker": normalized,
        "generated_at": utc_now_iso(),
        "status": status,
        "source_type": DIRECT if status == "available" else UNAVAILABLE,
        "score": round(score, 2),
        "label": label,
        "summary": f"{label}: 半年期日={price_setup['status_label']} / 信用={margin_setup['status_label']}",
        "items": items,
        "quality_warnings": warnings,
        "margin": margin_setup,
        "price_expiry": price_setup,
        "loan_alert": alert or {},
        "invalidation": invalidation,
    }


def _normalize_price_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = frame.copy()
    data.rename(columns={"close": "Close", "high": "High", "low": "Low"}, inplace=True)
    if "Close" not in data.columns:
        return pd.DataFrame()
    data["Close"] = pd.to_numeric(data["Close"], errors="coerce")
    if "High" not in data.columns:
        data["High"] = data["Close"]
    if "Low" not in data.columns:
        data["Low"] = data["Close"]
    data["High"] = pd.to_numeric(data["High"], errors="coerce")
    data["Low"] = pd.to_numeric(data["Low"], errors="coerce")
    return data.dropna(subset=["Close"])


def _price_expiry_setup(
    frame: pd.DataFrame, *, today: str | pd.Timestamp | None
) -> dict[str, Any]:
    if frame.empty or len(frame) < 120:
        return {
            "available": False,
            "near_high_expiry": False,
            "status_label": "データ不足",
            "detail": "半年期日を判定する価格履歴が不足しています。",
        }
    data = frame.tail(170)
    high_date = data["High"].idxmax()
    low_date = data["Low"].idxmin()
    current_date = (
        pd.Timestamp(today) if today is not None else pd.Timestamp(data.index[-1])
    )
    high_days = abs((current_date - pd.Timestamp(high_date)).days - 182)
    low_days = abs((current_date - pd.Timestamp(low_date)).days - 182)
    near_high = high_days <= 21
    return {
        "available": True,
        "near_high_expiry": bool(near_high),
        "near_low_expiry": bool(low_days <= 21),
        "days_from_high": int((current_date - pd.Timestamp(high_date)).days),
        "days_from_low": int((current_date - pd.Timestamp(low_date)).days),
        "status_label": "高値期日接近" if near_high else "期日条件未達",
        "detail": f"高値から{int((current_date - pd.Timestamp(high_date)).days)}日、安値から{int((current_date - pd.Timestamp(low_date)).days)}日。",
    }


def _margin_setup(rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not rows:
        return {
            "available": False,
            "system_margin_ratio": None,
            "ratio_signal": False,
            "buy_balance_improving": False,
            "status_label": "制度信用データ不足",
            "detail": "JPX/日証金または手入力の制度信用残高がありません。",
        }
    ordered = sorted(rows, key=lambda row: str(row.get("date") or ""))
    latest = ordered[-1]
    buy = _number(latest.get("system_buy_balance"))
    sell = _number(latest.get("system_sell_balance"))
    ratio = buy / sell if buy is not None and sell not in (None, 0) else None
    recent_buys = [
        _number(row.get("system_buy_balance"))
        for row in ordered[-4:]
        if _number(row.get("system_buy_balance")) is not None
    ]
    improving = len(recent_buys) >= 2 and recent_buys[-1] < recent_buys[0]
    ratio_signal = ratio is not None and ratio <= 1.05
    ratio_text = "算出不可" if ratio is None else f"{ratio:.2f}倍"
    return {
        "available": True,
        "system_margin_ratio": ratio,
        "ratio_signal": bool(ratio_signal),
        "buy_balance_improving": bool(improving),
        "status_label": "1倍近傍/逆転" if ratio_signal else "信用倍率未改善",
        "detail": f"制度信用倍率 {ratio_text} / 買い残整理={'あり' if improving else '未確認'}。",
    }


def _invalidation(
    frame: pd.DataFrame, rows: list[dict[str, Any]] | None
) -> dict[str, Any]:
    if frame.empty or len(frame) < 25:
        return {"available": False, "active": False, "detail": "価格履歴不足。"}
    close = frame["Close"].astype(float)
    drop_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0.0
    buy_increased = False
    if rows and len(rows) >= 2:
        ordered = sorted(rows, key=lambda row: str(row.get("date") or ""))
        old = _number(ordered[-2].get("system_buy_balance"))
        new = _number(ordered[-1].get("system_buy_balance"))
        buy_increased = old is not None and new is not None and new > old
    active = drop_20d <= -8.0 and buy_increased
    return {
        "available": True,
        "active": bool(active),
        "drop_20d": round(drop_20d, 2),
        "buy_balance_increased": bool(buy_increased),
        "detail": f"20日騰落 {drop_20d:+.2f}% / 買い残増加={'あり' if buy_increased else '未確認'}。",
    }


def _item(
    key: str,
    label: str,
    active: bool,
    detail: str,
    source_type: str,
    *,
    negative: bool = False,
) -> dict[str, Any]:
    status = "alert" if active and negative else "met" if active else "not_met"
    return {
        "key": key,
        "label": label,
        "status": status,
        "status_label": "無効化"
        if active and negative
        else "達成"
        if active
        else "未達",
        "source_type": source_type,
        "detail": detail,
    }


def _env_margin_rows(ticker: str) -> list[dict[str, Any]]:
    key = f"JP_MARGIN_ROWS_{ticker.replace('.', '_')}"
    raw = os.environ.get(key)
    if not raw:
        return []
    import json

    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _env_loan_alert(ticker: str) -> dict[str, Any]:
    key = f"JP_LOAN_ALERT_{ticker.replace('.', '_')}"
    raw = os.environ.get(key)
    if not raw:
        return {}
    return {
        "active": raw.strip().lower() in {"1", "true", "yes", "active"},
        "detail": raw,
    }


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number
