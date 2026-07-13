"""Probabilistic stock signal service."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.advisor.exposure_sizing import suggest_exposure
from src.advisor.regime_monitor import evaluate_regime
from src.advisor.signal_modeling import compare_signal_models
from src.advisor.stock_feature_engine import (
    build_stock_feature_frame,
    create_feature_snapshot,
)
from src.backtesting.walk_forward import run_walk_forward_validation
from src.display_labels import (
    ACTION_LABELS,
    CONFIDENCE_LABELS,
    SIGNAL_LABELS,
    display_label,
)

ROUND_TRIP_COST = 0.002


@dataclass
class ProbabilisticSignal:
    ticker: str
    signal_label: str
    expected_5d_return: float | None
    expected_20d_excess_return: float | None
    probability_up: float | None
    risk_adjusted_signal: float | None
    confidence: str
    regime_fit: float | None
    sample_size: int
    distribution: dict[str, float | int | None] = field(default_factory=dict)
    validation_summary: dict[str, Any] = field(default_factory=dict)
    risk_notes: list[str] = field(default_factory=list)
    suggested_action: str = "Watch"
    max_allocation_pct: int = 0
    feature_snapshot: dict[str, Any] = field(default_factory=dict)
    regime_monitor: dict[str, Any] = field(default_factory=dict)
    exposure_sizing: dict[str, Any] = field(default_factory=dict)
    model_comparison: dict[str, Any] = field(default_factory=dict)
    why_positive: list[str] = field(default_factory=list)
    why_negative: list[str] = field(default_factory=list)


def classify_signal_row(row: pd.Series) -> str:
    """Classify daily overextension using VWAP Z and return percentile."""

    vwap_z = row.get("vwap_deviation_z_120d")
    ret_pct = row.get("return_1d_percentile_252d")
    if pd.isna(vwap_z) or pd.isna(ret_pct):
        return "Neutral"

    if vwap_z <= -2.5 and ret_pct <= 5:
        return "Strong Oversold Rebound Candidate"
    if vwap_z <= -2.0 and ret_pct <= 10:
        return "Oversold Rebound Candidate"
    if vwap_z >= 2.5 and ret_pct >= 95:
        return "Strong Overbought Mean-Reversion Candidate"
    if vwap_z >= 2.0 and ret_pct >= 90:
        return "Overbought Mean-Reversion Candidate"
    return "Neutral"


def add_forward_outcomes(
    feature_frame: pd.DataFrame,
    price_df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach future returns and adverse/favorable excursion outcomes."""

    if feature_frame.empty:
        return feature_frame

    out = feature_frame.copy()
    prices = price_df.sort_index().reindex(out.index)
    close = pd.to_numeric(prices["Close"], errors="coerce")
    high = pd.to_numeric(prices["High"], errors="coerce")
    low = pd.to_numeric(prices["Low"], errors="coerce")

    out["forward_5d_return"] = close.shift(-5) / close - 1
    out["forward_20d_return"] = close.shift(-20) / close - 1

    mae_5d: list[float] = []
    mfe_5d: list[float] = []
    for idx in range(len(out)):
        current = close.iloc[idx]
        future_low = low.iloc[idx + 1 : idx + 6]
        future_high = high.iloc[idx + 1 : idx + 6]
        if pd.isna(current) or current == 0 or future_low.empty or future_high.empty:
            mae_5d.append(np.nan)
            mfe_5d.append(np.nan)
            continue
        mae_5d.append(float(future_low.min() / current - 1))
        mfe_5d.append(float(future_high.max() / current - 1))

    out["mae_5d"] = mae_5d
    out["mfe_5d"] = mfe_5d

    if benchmark_df is not None and not benchmark_df.empty:
        benchmark_close = benchmark_df.sort_index()["Close"].reindex(out.index).ffill()
        out["benchmark_forward_5d_return"] = (
            benchmark_close.shift(-5) / benchmark_close - 1
        )
        out["benchmark_forward_20d_return"] = (
            benchmark_close.shift(-20) / benchmark_close - 1
        )
        out["forward_20d_excess_return"] = (
            out["forward_20d_return"] - out["benchmark_forward_20d_return"]
        )
    else:
        out["benchmark_forward_5d_return"] = np.nan
        out["benchmark_forward_20d_return"] = np.nan
        out["forward_20d_excess_return"] = np.nan

    out["signal_label"] = out.apply(classify_signal_row, axis=1)
    return out.replace([np.inf, -np.inf], np.nan)


def _distribution_stats(rows: pd.DataFrame) -> dict[str, float | int | None]:
    if rows.empty:
        return {
            "sample_size": 0,
            "mean_5d": None,
            "median_5d": None,
            "p5_5d": None,
            "p25_5d": None,
            "p75_5d": None,
            "p95_5d": None,
            "probability_up": None,
            "mean_20d_excess": None,
            "mae_p5": None,
            "mfe_p95": None,
            "cost_adjusted_mean_5d": None,
        }

    fwd_5d = rows["forward_5d_return"].dropna() - ROUND_TRIP_COST
    fwd_20_excess = rows["forward_20d_excess_return"].dropna() - ROUND_TRIP_COST
    mae = rows["mae_5d"].dropna()
    mfe = rows["mfe_5d"].dropna()
    if fwd_5d.empty:
        return _distribution_stats(pd.DataFrame())

    return {
        "sample_size": int(len(fwd_5d)),
        "mean_5d": float(fwd_5d.mean()),
        "median_5d": float(fwd_5d.median()),
        "p5_5d": float(fwd_5d.quantile(0.05)),
        "p25_5d": float(fwd_5d.quantile(0.25)),
        "p75_5d": float(fwd_5d.quantile(0.75)),
        "p95_5d": float(fwd_5d.quantile(0.95)),
        "probability_up": float((fwd_5d > 0).mean()),
        "mean_20d_excess": float(fwd_20_excess.mean())
        if not fwd_20_excess.empty
        else None,
        "mae_p5": float(mae.quantile(0.05)) if not mae.empty else None,
        "mfe_p95": float(mfe.quantile(0.95)) if not mfe.empty else None,
        "cost_adjusted_mean_5d": float(fwd_5d.mean()),
    }


def _realized_vol_percentile(feature_frame: pd.DataFrame) -> float | None:
    if "realized_vol_20d" not in feature_frame.columns or feature_frame.empty:
        return None
    history = feature_frame["realized_vol_20d"].dropna()
    if len(history) < 30:
        return None
    latest = history.iloc[-1]
    return float((history <= latest).mean() * 100)


def _risk_adjusted_signal(
    expected_return: float | None, latest_vol: float | None
) -> float | None:
    if (
        expected_return is None
        or latest_vol is None
        or latest_vol <= 0
        or not np.isfinite(latest_vol)
    ):
        return None
    five_day_vol = latest_vol / np.sqrt(252) * np.sqrt(5)
    if five_day_vol <= 0:
        return None
    return float(expected_return / five_day_vol)


def _confidence(
    sample_size: int,
    validation: dict[str, Any],
    regime_fit: float | None,
) -> str:
    if sample_size < 30 or regime_fit is None or regime_fit < 50:
        return "Low"
    fold_count = len(validation.get("folds", []))
    outperformance = validation.get("outperformance_count", 0)
    if sample_size >= 100 and fold_count > 0 and outperformance / fold_count >= 0.60:
        return "High"
    return "Medium"


def _risk_notes(
    distribution: dict[str, float | int | None],
    regime: dict[str, Any],
    confidence: str,
) -> list[str]:
    notes = list(regime.get("notes", []))
    if confidence == "Low":
        notes.append("Confidence is Low; treat the signal as exploratory.")
    if distribution.get("sample_size", 0) < 30:
        notes.append("Similar historical sample is small.")
    if distribution.get("mean_5d") is not None and distribution["mean_5d"] <= 0:
        notes.append("Cost-adjusted 5D expected return is not positive.")
    if distribution.get("mae_p5") is not None:
        notes.append(f"Adverse 5D tail observed near {distribution['mae_p5']:.2%}.")
    return notes[:6]


def _why_lists(latest: pd.Series, signal_label: str) -> tuple[list[str], list[str]]:
    positives: list[str] = []
    negatives: list[str] = []

    if "Oversold" in signal_label:
        positives.append(
            "VWAP deviation and return percentile indicate an oversold setup."
        )
    if "Overbought" in signal_label:
        negatives.append(
            "VWAP deviation and return percentile indicate an overbought setup."
        )

    if latest.get("return_20d", 0) > 0:
        positives.append("20D momentum is positive.")
    elif latest.get("return_20d", 0) < 0:
        negatives.append("20D momentum is negative.")

    if latest.get("volume_zscore_20d", 0) > 1.5:
        positives.append("Volume is unusually elevated versus its 20D history.")

    if latest.get("realized_vol_20d", 0) > latest.get("realized_vol_60d", np.inf):
        negatives.append("Short-term volatility is above longer-term volatility.")

    if latest.get("pe_ratio") and latest.get("pe_ratio") > 50:
        negatives.append("Valuation is stretched on trailing PE.")

    if not positives:
        positives.append(
            "No strong positive factor; signal relies on distributional evidence."
        )
    if not negatives:
        negatives.append(
            "No dominant negative factor detected in the current feature set."
        )
    return positives[:4], negatives[:4]


def _fallback_signal(ticker: str, reason: str) -> ProbabilisticSignal:
    return ProbabilisticSignal(
        ticker=ticker,
        signal_label="Insufficient data",
        expected_5d_return=None,
        expected_20d_excess_return=None,
        probability_up=None,
        risk_adjusted_signal=None,
        confidence="Low",
        regime_fit=None,
        sample_size=0,
        risk_notes=[reason],
        suggested_action="Watch",
        max_allocation_pct=0,
    )


def generate_probabilistic_stock_signal(
    ticker: str,
    period: str = "5y",
    benchmark: str = "SPY",
    stock_info: dict[str, Any] | None = None,
    technical_data: dict[str, Any] | None = None,
    price_df: pd.DataFrame | None = None,
    benchmark_df: pd.DataFrame | None = None,
) -> ProbabilisticSignal:
    """Generate a complete probabilistic signal from existing free data."""

    from src.market_data import get_stock_data, get_stock_info

    price_df = price_df if price_df is not None else get_stock_data(ticker, period)
    if price_df is None or price_df.empty or len(price_df) < 80:
        return _fallback_signal(ticker, "Insufficient price history.")

    benchmark_df = (
        benchmark_df if benchmark_df is not None else get_stock_data(benchmark, period)
    )
    info = (
        stock_info
        if stock_info is not None
        else get_stock_info(ticker, translate_summary=False)
    )
    feature_frame = build_stock_feature_frame(
        price_df, benchmark_df, info, technical_data
    )
    if feature_frame.empty:
        return _fallback_signal(ticker, "Feature generation failed.")

    feature_frame = add_forward_outcomes(feature_frame, price_df, benchmark_df)
    latest = feature_frame.iloc[-1]
    signal_label = classify_signal_row(latest)
    historical = feature_frame.dropna(subset=["forward_5d_return"]).copy()
    similar = historical[historical["signal_label"] == signal_label]
    distribution = _distribution_stats(similar)

    expected_5d = _optional_float(distribution.get("mean_5d"))
    expected_20d_excess = _optional_float(distribution.get("mean_20d_excess"))
    probability_up = _optional_float(distribution.get("probability_up"))
    latest_vol = latest.get("realized_vol_20d")
    latest_vol_float = float(latest_vol) if pd.notna(latest_vol) else None
    risk_adjusted = _risk_adjusted_signal(expected_5d, latest_vol_float)

    validation = run_walk_forward_validation(feature_frame, signal_label)
    regime = evaluate_regime(feature_frame)
    regime_fit = _optional_float(regime.get("regime_fit"))
    confidence = _confidence(
        int(distribution.get("sample_size") or 0),
        validation,
        regime_fit,
    )
    exposure = suggest_exposure(
        expected_return=expected_5d,
        risk_adjusted_signal=risk_adjusted,
        confidence=confidence,
        realized_vol_20d=latest_vol_float,
        realized_vol_percentile=_realized_vol_percentile(feature_frame),
        adverse_loss_p95=abs(float(distribution["mae_p5"]))
        if distribution.get("mae_p5") is not None
        else None,
        regime_fit=regime_fit,
    )
    if signal_label in {"Neutral", "Insufficient data"} or confidence == "Low":
        exposure["suggested_action"] = "Watch"
        exposure["max_allocation_pct"] = 0
        exposure["size_multiplier"] = 0.0
        exposure.setdefault("risk_cap_notes", []).append(
            "Neutral or low-confidence signals are observation-only."
        )
    snapshot = create_feature_snapshot(ticker, feature_frame)
    positives, negatives = _why_lists(latest, signal_label)

    return ProbabilisticSignal(
        ticker=ticker,
        signal_label=signal_label,
        expected_5d_return=_optional_round(expected_5d, 6),
        expected_20d_excess_return=_optional_round(expected_20d_excess, 6),
        probability_up=_optional_round(probability_up, 4),
        risk_adjusted_signal=_optional_round(risk_adjusted, 4),
        confidence=confidence,
        regime_fit=regime_fit,
        sample_size=int(distribution.get("sample_size") or 0),
        distribution=distribution,
        validation_summary=validation,
        risk_notes=_risk_notes(distribution, regime, confidence),
        suggested_action=exposure["suggested_action"],
        max_allocation_pct=int(exposure["max_allocation_pct"]),
        feature_snapshot=asdict(snapshot),
        regime_monitor=regime,
        exposure_sizing=exposure,
        model_comparison=compare_signal_models(feature_frame),
        why_positive=positives,
        why_negative=negatives,
    )


def signal_to_dict(signal: ProbabilisticSignal) -> dict[str, Any]:
    """Serialize signal for Reflex state."""

    data = asdict(signal)
    data["signal_label_display"] = display_label(signal.signal_label, SIGNAL_LABELS)
    data["suggested_action_display"] = display_label(
        signal.suggested_action, ACTION_LABELS
    )
    data["confidence_display"] = display_label(signal.confidence, CONFIDENCE_LABELS)
    data["expected_5d_return_display"] = _percent_display(
        signal.expected_5d_return, digits=2, signed=True
    )
    data["expected_20d_excess_return_display"] = _percent_display(
        signal.expected_20d_excess_return, digits=2, signed=True
    )
    data["probability_up_display"] = _percent_display(signal.probability_up, digits=1)
    data["risk_adjusted_signal_display"] = _number_display(
        signal.risk_adjusted_signal, digits=2, signed=True
    )
    data["regime_fit_display"] = (
        "算出不可" if signal.regime_fit is None else f"{signal.regime_fit:.0f}%"
    )
    data["max_allocation_display"] = f"{signal.max_allocation_pct}%"
    data["sample_size_display"] = str(signal.sample_size)
    data["walk_forward_summary"] = signal.validation_summary.get(
        "summary", "Walk-forward unavailable."
    )
    data["selected_model"] = signal.model_comparison.get("selected_model", "Baseline")
    data["volatility_regime"] = signal.regime_monitor.get(
        "volatility_regime", "Unknown"
    )
    data["trend_regime"] = signal.regime_monitor.get("trend_regime", "Unknown")
    data["risk_notes_display"] = "\n".join(f"- {item}" for item in signal.risk_notes)
    data["why_positive_display"] = "\n".join(
        f"- {item}" for item in signal.why_positive
    )
    data["why_negative_display"] = "\n".join(
        f"- {item}" for item in signal.why_negative
    )
    return data


def _percent_display(value: float | None, *, digits: int, signed: bool = False) -> str:
    """Format a probability or return without inventing a numeric zero."""

    if value is None:
        return "算出不可"
    sign = "+" if signed else ""
    return f"{value:{sign}.{digits}%}"


def _number_display(value: float | None, *, digits: int, signed: bool = False) -> str:
    """Format a model value while preserving unavailable semantics."""

    if value is None:
        return "算出不可"
    sign = "+" if signed else ""
    return f"{value:{sign}.{digits}f}"


def _optional_float(value: Any) -> float | None:
    """Return a finite float while preserving unavailable values."""

    if value is None or pd.isna(value):
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def _optional_round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)
