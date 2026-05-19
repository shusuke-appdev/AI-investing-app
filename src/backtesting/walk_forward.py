"""Walk-forward validation for probabilistic stock signals."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def _profit_factor(returns: pd.Series) -> float:
    gains = returns[returns > 0].sum()
    losses = returns[returns < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / abs(losses))


def _fold_metrics(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    horizon: int,
    cost: float,
    test_size: int,
) -> dict[str, Any]:
    if returns.empty:
        return {
            "trade_count": 0,
            "mean_return": 0.0,
            "cagr": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "hit_rate": 0.0,
            "profit_factor": 0.0,
            "turnover": 0.0,
            "cost_impact": 0.0,
            "benchmark_alpha": 0.0,
        }

    clean = returns.dropna()
    periods_per_year = 252 / horizon
    mean_return = float(clean.mean())
    std = float(clean.std())
    sharpe = mean_return / std * np.sqrt(periods_per_year) if std > 0 else 0.0
    cagr = float((1.0 + mean_return) ** periods_per_year - 1.0)
    benchmark_mean = (
        float(benchmark_returns.dropna().mean()) if not benchmark_returns.empty else 0.0
    )

    return {
        "trade_count": int(len(clean)),
        "mean_return": mean_return,
        "cagr": cagr,
        "sharpe": float(sharpe),
        "max_drawdown": _max_drawdown(clean),
        "hit_rate": float((clean > 0).mean()),
        "profit_factor": _profit_factor(clean),
        "turnover": float(len(clean) / max(test_size, 1) * periods_per_year),
        "cost_impact": float(cost * len(clean)),
        "benchmark_alpha": mean_return - benchmark_mean,
    }


def run_walk_forward_validation(
    feature_frame: pd.DataFrame,
    target_label: str,
    horizon: int = 5,
    train_days: int = 756,
    test_days: int = 252,
    step_days: int = 252,
    round_trip_cost_bps: float = 20.0,
) -> dict[str, Any]:
    """Validate a fixed signal label with rolling train/test windows."""

    required = {"signal_label", f"forward_{horizon}d_return"}
    if feature_frame.empty or not required.issubset(feature_frame.columns):
        return {
            "folds": [],
            "pass_count": 0,
            "outperformance_count": 0,
            "worst_fold_return": 0.0,
            "summary": "Walk-forward unavailable: insufficient data.",
            "execution_proxy_used": True,
        }

    clean = feature_frame.dropna(subset=[f"forward_{horizon}d_return"]).copy()
    if len(clean) < train_days + test_days:
        return {
            "folds": [],
            "pass_count": 0,
            "outperformance_count": 0,
            "worst_fold_return": 0.0,
            "summary": "Walk-forward unavailable: not enough history.",
            "execution_proxy_used": True,
        }

    cost = round_trip_cost_bps / 10000.0
    folds: list[dict[str, Any]] = []
    start = 0
    while start + train_days + test_days <= len(clean):
        test_start = start + train_days
        test_end = test_start + test_days
        test = clean.iloc[test_start:test_end]
        active = test[test["signal_label"] == target_label]
        returns = active[f"forward_{horizon}d_return"] - cost
        benchmark_col = f"benchmark_forward_{horizon}d_return"
        benchmark_returns = (
            active[benchmark_col]
            if benchmark_col in active.columns
            else pd.Series(dtype=float)
        )
        metrics = _fold_metrics(returns, benchmark_returns, horizon, cost, len(test))
        metrics["train_start"] = (
            str(clean.index[start].date())
            if hasattr(clean.index[start], "date")
            else str(clean.index[start])
        )
        metrics["test_start"] = (
            str(test.index[0].date())
            if hasattr(test.index[0], "date")
            else str(test.index[0])
        )
        metrics["test_end"] = (
            str(test.index[-1].date())
            if hasattr(test.index[-1], "date")
            else str(test.index[-1])
        )
        folds.append(metrics)
        start += step_days

    pass_count = sum(1 for fold in folds if fold["mean_return"] > 0)
    outperformance_count = sum(1 for fold in folds if fold["benchmark_alpha"] > 0)
    worst_fold_return = min((fold["mean_return"] for fold in folds), default=0.0)

    return {
        "folds": folds,
        "pass_count": int(pass_count),
        "outperformance_count": int(outperformance_count),
        "worst_fold_return": float(worst_fold_return),
        "summary": f"Walk-forward: {outperformance_count}/{len(folds)} folds beat benchmark.",
        "execution_proxy_used": True,
    }
