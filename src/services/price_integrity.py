"""Reject suspect mixed price bases without guessing a split adjustment."""

from __future__ import annotations

import numpy as np
import pandas as pd


def price_integrity(frame: pd.DataFrame | None) -> dict:
    if frame is None or frame.empty or "Close" not in frame:
        return {"status": "insufficient", "reason": "価格履歴が不足しています。"}
    if not pd.api.types.is_numeric_dtype(frame["Close"]) or pd.api.types.is_bool_dtype(
        frame["Close"]
    ):
        return {
            "status": "invalid",
            "reason": "価格の型が数値ではありません。文字・真偽値を価格へ変換しません。",
        }
    close = pd.to_numeric(frame["Close"], errors="coerce")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        return {"status": "invalid", "reason": "価格日付の重複・順序不整合。"}
    if close.isna().any() or not np.isfinite(close).all() or (close <= 0).any():
        return {"status": "invalid", "reason": "非有限・非正・欠損の価格が存在します。"}
    ratios = close / close.shift(1)
    if {"High", "Low"} <= set(frame.columns):
        high, low = (
            pd.to_numeric(frame["High"], errors="coerce"),
            pd.to_numeric(frame["Low"], errors="coerce"),
        )
        if ((high * 1.000001 < close) | (low > close * 1.000001) | (high < low)).any():
            return {
                "status": "suspect_price_basis",
                "reason": "終値・高値・安値の価格基準が整合しません。派生判定を停止します。",
            }
    if ((ratios > 4) | (ratios < 0.25)).any():
        return {
            "status": "suspect_price_basis",
            "reason": "価格基準の急な不連続。分割・調整基準を原系列と会社資料で確認するまで派生判定を停止します。",
        }
    return {"status": "ok", "reason": "倍率を推測した自動補正は行っていません。"}


def usable_history(frame: pd.DataFrame) -> pd.DataFrame:
    prior = frame.attrs.get("price_integrity", {})
    quality = (
        prior if prior.get("status") not in {None, "ok"} else price_integrity(frame)
    )
    result = frame.copy() if quality["status"] == "ok" else frame.iloc[:0].copy()
    result.attrs["price_integrity"] = quality
    return result
