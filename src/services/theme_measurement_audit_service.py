"""Offline bias audit for versioned theme measurement baskets."""

from __future__ import annotations

from typing import Any, TypedDict

import numpy as np
import pandas as pd

from src.advisor.price_action_metrics import normalize_price_frame

MIN_RETURN_CORRELATION = 0.90
MIN_DIRECTION_AGREEMENT = 0.85
MIN_RANK_CORRELATION = 0.92
MIN_TOP10_OVERLAP = 0.80
PERIODS = (5, 21, 126)


class ThemeBasketAudit(TypedDict, total=False):
    theme: str
    all_count: int
    measurement_count: int
    correlation_20d: float
    correlation_63d: float
    direction_agreement: float
    passed: bool
    reason: str


class ThemeMeasurementAuditContext(TypedDict, total=False):
    status: str
    baskets: dict[str, list[str]]
    theme_audits: dict[str, ThemeBasketAudit]
    rank_correlation_1w: float
    rank_correlation_1m: float
    rank_correlation_6m: float
    top10_overlap_1w: float
    top10_overlap_1m: float
    top10_overlap_6m: float
    passed: bool
    warnings: list[str]


def build_audited_measurement_baskets(
    *,
    themes: dict[str, list[str]],
    price_frames: dict[str, pd.DataFrame],
) -> ThemeMeasurementAuditContext:
    """Select the smallest proven baskets; retain all names when proof fails."""

    ordered = {
        theme: _stable_ticker_order(tickers, price_frames)
        for theme, tickers in themes.items()
    }
    baskets = {
        theme: tickers[: min(4, len(tickers))] for theme, tickers in ordered.items()
    }
    theme_audits: dict[str, ThemeBasketAudit] = {}
    for theme, all_tickers in ordered.items():
        selected = list(baskets[theme])
        audit = _audit_one_theme(theme, all_tickers, selected, price_frames)
        while not audit["passed"] and len(selected) < len(all_tickers):
            selected.append(all_tickers[len(selected)])
            audit = _audit_one_theme(theme, all_tickers, selected, price_frames)
        if not audit["passed"]:
            selected = list(all_tickers)
            audit = _audit_one_theme(theme, all_tickers, selected, price_frames)
        baskets[theme] = selected
        theme_audits[theme] = audit

    global_audit = _global_rank_audit(themes, baskets, price_frames)
    while not global_audit["passed"]:
        expandable = [
            theme
            for theme, tickers in ordered.items()
            if len(baskets[theme]) < len(tickers)
        ]
        if not expandable:
            break
        expandable.sort(
            key=lambda theme: (
                min(
                    float(theme_audits[theme]["correlation_20d"]),
                    float(theme_audits[theme]["correlation_63d"]),
                    float(theme_audits[theme]["direction_agreement"]),
                ),
                theme,
            )
        )
        theme = expandable[0]
        baskets[theme].append(ordered[theme][len(baskets[theme])])
        theme_audits[theme] = _audit_one_theme(
            theme, ordered[theme], baskets[theme], price_frames
        )
        global_audit = _global_rank_audit(themes, baskets, price_frames)

    passed = bool(global_audit["passed"]) and all(
        bool(theme_audits[theme]["passed"])
        or len(baskets[theme]) == len(ordered[theme])
        for theme in ordered
    )
    if not passed:
        baskets = {theme: list(tickers) for theme, tickers in ordered.items()}
        theme_audits = {
            theme: _audit_one_theme(theme, tickers, tickers, price_frames)
            for theme, tickers in ordered.items()
        }
        global_audit = _global_rank_audit(themes, baskets, price_frames)
        passed = bool(global_audit["passed"])

    warnings = []
    retained_without_proof = sum(
        not audit["passed"] and len(baskets[theme]) == len(ordered[theme])
        for theme, audit in theme_audits.items()
    )
    if retained_without_proof:
        warnings.append(
            f"証拠不足の{retained_without_proof}テーマは削減せず全構成銘柄を維持します。"
        )
    if not passed:
        warnings.append(
            "取得履歴だけでは偏り基準を証明できないため、全構成銘柄を維持します。"
        )
    return {
        "status": "available" if passed else "insufficient_evidence",
        "baskets": baskets,
        "theme_audits": theme_audits,
        **global_audit,
        "passed": passed,
        "warnings": warnings,
    }


def audit_measurement_baskets(
    *,
    themes: dict[str, list[str]],
    baskets: dict[str, list[str]],
    price_frames: dict[str, pd.DataFrame],
) -> ThemeMeasurementAuditContext:
    """Check an existing versioned selection without changing it."""

    theme_audits = {
        theme: _audit_one_theme(
            theme,
            list(dict.fromkeys(tickers)),
            list(dict.fromkeys(baskets.get(theme) or [])),
            price_frames,
        )
        for theme, tickers in themes.items()
    }
    global_audit = _global_rank_audit(themes, baskets, price_frames)
    passed = bool(global_audit["passed"]) and all(
        bool(theme_audits[theme]["passed"])
        or len(baskets.get(theme) or []) == len(list(dict.fromkeys(tickers)))
        for theme, tickers in themes.items()
    )
    return {
        "status": "available" if passed else "insufficient_evidence",
        "baskets": baskets,
        "theme_audits": theme_audits,
        **global_audit,
        "passed": passed,
        "warnings": [] if passed else ["代表銘柄監査の基準を満たしていません。"],
    }


def _audit_one_theme(
    theme: str,
    all_tickers: list[str],
    measurement_tickers: list[str],
    price_frames: dict[str, pd.DataFrame],
) -> ThemeBasketAudit:
    full20 = _median_return_series(all_tickers, price_frames, 20)
    full63 = _median_return_series(all_tickers, price_frames, 63)
    sample20 = _median_return_series(measurement_tickers, price_frames, 20)
    sample63 = _median_return_series(measurement_tickers, price_frames, 63)
    corr20 = _correlation(full20, sample20)
    corr63 = _correlation(full63, sample63)
    direction = (
        _direction_agreement(full20, sample20) + _direction_agreement(full63, sample63)
    ) / 2
    available_count = sum(
        len(normalize_price_frame(price_frames.get(ticker, pd.DataFrame()))) >= 127
        for ticker in all_tickers
    )
    evidence_ok = available_count >= min(3, len(all_tickers))
    passed = (
        evidence_ok
        and corr20 >= MIN_RETURN_CORRELATION
        and corr63 >= MIN_RETURN_CORRELATION
        and direction >= MIN_DIRECTION_AGREEMENT
    )
    return {
        "theme": theme,
        "all_count": len(all_tickers),
        "measurement_count": len(measurement_tickers),
        "correlation_20d": round(corr20, 4),
        "correlation_63d": round(corr63, 4),
        "direction_agreement": round(direction, 4),
        "passed": passed,
        "reason": "" if passed else "相関・方向一致または取得履歴が基準未達",
    }


def _global_rank_audit(
    themes: dict[str, list[str]],
    baskets: dict[str, list[str]],
    price_frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    passed = True
    labels = {5: "1w", 21: "1m", 126: "6m"}
    for period in PERIODS:
        full_values = {}
        sample_values = {}
        for theme, all_tickers in themes.items():
            full = _latest_median_return(all_tickers, price_frames, period)
            sample = _latest_median_return(
                baskets.get(theme) or [], price_frames, period
            )
            if full is not None and sample is not None:
                full_values[theme] = full
                sample_values[theme] = sample
        common = sorted(set(full_values) & set(sample_values))
        if len(common) < 3:
            rank_corr = 0.0
            overlap = 0.0
        else:
            full_series = pd.Series([full_values[key] for key in common], index=common)
            sample_series = pd.Series(
                [sample_values[key] for key in common], index=common
            )
            raw_corr = full_series.corr(sample_series, method="spearman")
            rank_corr = float(raw_corr) if pd.notna(raw_corr) else 0.0
            top_count = min(10, len(common))
            full_top = set(full_series.nlargest(top_count).index)
            sample_top = set(sample_series.nlargest(top_count).index)
            overlap = len(full_top & sample_top) / top_count
        label = labels[period]
        result[f"rank_correlation_{label}"] = round(rank_corr, 4)
        result[f"top10_overlap_{label}"] = round(overlap, 4)
        passed = (
            passed
            and rank_corr >= MIN_RANK_CORRELATION
            and overlap >= MIN_TOP10_OVERLAP
        )
    result["passed"] = passed
    return result


def _stable_ticker_order(
    tickers: list[str], price_frames: dict[str, pd.DataFrame]
) -> list[str]:
    unique = list(dict.fromkeys(str(ticker).upper() for ticker in tickers))

    def quality(ticker: str) -> tuple[int, float, str]:
        frame = normalize_price_frame(price_frames.get(ticker, pd.DataFrame()))
        coverage = min(len(frame) / 504, 1.0)
        dollar_volume = 0.0
        if len(frame) >= 20 and "Volume" in frame:
            value = (
                (frame["Close"].astype(float) * frame["Volume"].astype(float))
                .tail(20)
                .median()
            )
            dollar_volume = float(value) if np.isfinite(value) else 0.0
        return (-round(coverage, 6), -dollar_volume, ticker)

    return sorted(unique, key=quality)


def _median_return_series(
    tickers: list[str],
    price_frames: dict[str, pd.DataFrame],
    period: int,
) -> pd.Series:
    values = []
    for ticker in tickers:
        frame = normalize_price_frame(price_frames.get(ticker, pd.DataFrame()))
        if len(frame) <= period:
            continue
        values.append(frame["Close"].astype(float).pct_change(period).rename(ticker))
    if not values:
        return pd.Series(dtype=float)
    return pd.concat(values, axis=1).median(axis=1, skipna=True).dropna()


def _latest_median_return(
    tickers: list[str],
    price_frames: dict[str, pd.DataFrame],
    period: int,
) -> float | None:
    values = []
    for ticker in tickers:
        frame = normalize_price_frame(price_frames.get(ticker, pd.DataFrame()))
        if len(frame) <= period:
            continue
        close = frame["Close"].astype(float)
        value = float((close.iloc[-1] / close.iloc[-period - 1] - 1) * 100)
        if np.isfinite(value):
            values.append(value)
    return float(pd.Series(values).median()) if values else None


def _correlation(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left, right], axis=1, join="inner").dropna()
    if len(aligned) < 30:
        return 0.0
    if aligned.iloc[:, 0].equals(aligned.iloc[:, 1]):
        return 1.0
    value = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
    return float(value) if pd.notna(value) else 0.0


def _direction_agreement(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left, right], axis=1, join="inner").dropna()
    if aligned.empty:
        return 0.0
    same = np.sign(aligned.iloc[:, 0]) == np.sign(aligned.iloc[:, 1])
    return float(same.mean())
