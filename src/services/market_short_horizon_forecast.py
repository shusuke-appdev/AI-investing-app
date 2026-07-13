"""Validated short-horizon SPY/QQQ forecasts built from point-in-time market data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import expit

from src.market_data import get_stock_data
from src.market_volatility_intelligence import CboeIndexResult, fetch_cboe_indices
from src.persistent_cache import repo_state_cache, utc_now_iso
from src.services.cftc_positioning_service import (
    CftcPositioningResult,
    fetch_cftc_positioning,
)

MODEL_VERSION = "market-short-horizon-v1"
FORECAST_TICKERS = ("SPY", "QQQ")
INPUT_TICKERS = ("SPY", "QQQ", "RSP", "IWM", "HYG", "IEF", "XLY", "XLP", "SMH")
HORIZONS = (1, 5, 20)
MIN_TRAIN_ROWS = 1260
OOS_TARGET_ROWS = 504
MIN_OOS_ROWS = 500
REFIT_STEP = 21
MIN_FEATURE_COVERAGE = 0.80
MIN_ANALOGS = 30
MAX_ANALOGS = 50


@dataclass
class ProbabilityFit:
    predictions: np.ndarray
    coefficients: pd.Series


def build_market_short_horizon_forecast(
    *,
    history_provider: Callable[[str, str], pd.DataFrame] = get_stock_data,
    cboe_result: CboeIndexResult | None = None,
    cftc_result: CftcPositioningResult | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch inputs and return a cached, validation-aware forecast bundle."""

    cache = repo_state_cache("market_short_horizon_forecast")
    cached = cache.read("us", fresh_seconds=6 * 3600, stale_seconds=72 * 3600)
    if cached.status == "fresh" and not force_refresh:
        return {**cached.payload, "cache_status": "persistent_cache"}

    try:
        frames = {ticker: history_provider(ticker, "10y") for ticker in INPUT_TICKERS}
        cboe = cboe_result or fetch_cboe_indices()
        cftc = cftc_result or fetch_cftc_positioning()
        result = compute_market_short_horizon_forecast(frames, cboe, cftc)
        cache.write("us", result, fetched_at=result.get("fetched_at") or utc_now_iso())
        return result
    except Exception as exc:
        if cached.is_available:
            return {
                **cached.payload,
                "is_stale": True,
                "cache_status": "stale_cache",
                "quality_warnings": [
                    *list(cached.payload.get("quality_warnings") or []),
                    f"Forecast refresh failed: {exc}",
                ],
            }
        return _unavailable_bundle(str(exc))


def compute_market_short_horizon_forecast(
    price_frames: dict[str, pd.DataFrame],
    cboe_result: CboeIndexResult,
    cftc_result: CftcPositioningResult | None = None,
) -> dict[str, Any]:
    """Compute all target/horizon forecasts from supplied point-in-time histories."""

    targets: dict[str, Any] = {}
    warnings = list(cboe_result.warnings)
    if cftc_result:
        warnings.extend(cftc_result.warnings)
    for ticker in FORECAST_TICKERS:
        close = _close(price_frames.get(ticker))
        if len(close) < MIN_TRAIN_ROWS + 60:
            targets[ticker] = {
                "status": "insufficient_data",
                "summary": f"{ticker}: 学習履歴が不足しています。",
                "horizons": {},
            }
            continue
        features = build_market_feature_frame(
            ticker,
            price_frames,
            cboe_result.data,
            cftc_result.data
            if cftc_result and cftc_result.status == "available"
            else None,
        )
        horizons: dict[str, Any] = {}
        for horizon in HORIZONS:
            horizons[f"{horizon}d"] = _forecast_horizon(
                ticker,
                horizon,
                close,
                features,
                cboe_result.data,
            )
        targets[ticker] = {
            "status": _target_status(horizons),
            "summary": _target_summary(ticker, horizons),
            "horizons": horizons,
        }

    statuses = [item.get("status") for item in targets.values()]
    status = (
        "validated"
        if statuses and all(item == "validated" for item in statuses)
        else "research_only"
    )
    if not targets or all(
        item in {"insufficient_data", "unavailable"} for item in statuses
    ):
        status = "unavailable"
    source_parts = ["cboe_official", "yfinance_cached", "deterministic_models"]
    if cftc_result and cftc_result.status == "available":
        source_parts.insert(1, "cftc_official")
    return {
        "status": status,
        "model_version": MODEL_VERSION,
        "as_of": _bundle_as_of(targets),
        "fetched_at": utc_now_iso(),
        "targets": targets,
        "source": "+".join(source_parts),
        "is_stale": bool(cboe_result.is_stale),
        "is_partial": bool(cboe_result.is_partial) or status != "validated",
        "cache_status": "computed",
        "quality_warnings": warnings,
        "integration_enabled": status == "validated" and not cboe_result.is_stale,
    }


def build_market_feature_frame(
    target: str,
    price_frames: dict[str, pd.DataFrame],
    cboe: pd.DataFrame,
    cftc: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build predeclared, explainable market features for one target."""

    close = _close(price_frames.get(target))
    frame = pd.DataFrame(index=close.index)
    returns = close.pct_change()
    frame["target_return_1d"] = returns
    frame["target_return_5d"] = close.pct_change(5)
    frame["target_return_20d"] = close.pct_change(20)
    frame["target_ma20_distance"] = close / close.rolling(20).mean() - 1
    frame["target_drawdown_63d"] = close / close.rolling(63).max() - 1
    frame["target_realized_vol_5d"] = returns.rolling(5).std() * np.sqrt(252)
    frame["target_realized_vol_20d"] = returns.rolling(20).std() * np.sqrt(252)
    volume = _volume(price_frames.get(target)).reindex(frame.index)
    frame["target_volume_z20"] = _rolling_z(volume, 20, 10)

    pairs = (
        ("RSP", "SPY"),
        ("IWM", "SPY"),
        ("HYG", "IEF"),
        ("XLY", "XLP"),
        ("QQQ", "SPY"),
        ("SMH", "QQQ"),
    )
    for left, right in pairs:
        ratio = _relative_series(price_frames, left, right).reindex(frame.index)
        key = f"relative_{left.lower()}_{right.lower()}"
        frame[f"{key}_5d"] = ratio.pct_change(5)
        frame[f"{key}_20d"] = ratio.pct_change(20)

    cboe_daily = _normalize_index(cboe).reindex(frame.index).ffill(limit=3)
    for symbol in (
        "VIX",
        "VIX1D",
        "VIX9D",
        "VIX3M",
        "VVIX",
        "SKEW",
        "VXN",
        "DSPX",
        "VIXEQ",
    ):
        if symbol not in cboe_daily:
            continue
        series = pd.to_numeric(cboe_daily[symbol], errors="coerce")
        key = symbol.lower()
        frame[f"{key}_level"] = series
        frame[f"{key}_change_5d"] = series.pct_change(5)
        frame[f"{key}_z252"] = _rolling_z(series, 252, 60)

    frame["vix1d_vix"] = _safe_ratio_column(frame, "vix1d_level", "vix_level")
    frame["vix9d_vix"] = _safe_ratio_column(frame, "vix9d_level", "vix_level")
    frame["vix_vix3m"] = _safe_ratio_column(frame, "vix_level", "vix3m_level")
    frame["vxn_vix"] = _safe_ratio_column(frame, "vxn_level", "vix_level")
    frame["interaction_vix_skew"] = (
        frame.get("vix_change_5d") * frame.get("skew_z252")
        if {"vix_change_5d", "skew_z252"}.issubset(frame)
        else np.nan
    )
    frame["interaction_vix_vvix"] = (
        frame.get("vix_change_5d") * frame.get("vvix_change_5d")
        if {"vix_change_5d", "vvix_change_5d"}.issubset(frame)
        else np.nan
    )
    breadth = frame.get("relative_rsp_spy_5d")
    frame["interaction_term_breadth"] = (
        (frame.get("vix_vix3m") - 1) * breadth
        if breadth is not None and "vix_vix3m" in frame
        else np.nan
    )
    if cftc is not None and not cftc.empty:
        positioning = _normalize_index(cftc).reindex(frame.index).ffill(limit=8)
        for column in (
            "cftc_asset_manager_net_oi",
            "cftc_leveraged_money_net_oi",
        ):
            if column not in positioning:
                continue
            series = pd.to_numeric(positioning[column], errors="coerce")
            frame[column] = series
            frame[f"{column}_change_4w"] = series.diff(4 * 5)
            frame[f"{column}_z156w"] = _rolling_z(series, 156 * 5, 52 * 5)
    return frame.replace([np.inf, -np.inf], np.nan).sort_index()


def _forecast_horizon(
    ticker: str,
    horizon: int,
    close: pd.Series,
    features: pd.DataFrame,
    cboe: pd.DataFrame,
) -> dict[str, Any]:
    forward = close.shift(-horizon) / close - 1
    required = {
        "vix_level",
        "vvix_level",
        "skew_level",
        "vix9d_vix",
        "vix_vix3m",
    }
    if horizon == 1:
        required.add("vix1d_level")
    missing_required = sorted(
        name
        for name in required
        if name not in features or pd.isna(features[name].iloc[-1])
    )
    if missing_required:
        return _insufficient_horizon(
            ticker,
            horizon,
            0.0,
            "Required current sentiment inputs are missing: "
            + ", ".join(missing_required),
        )
    selected = _select_features(features, horizon)
    current_row = features[selected].iloc[-1] if selected else pd.Series(dtype=float)
    current_coverage = float(current_row.notna().mean()) if len(current_row) else 0.0
    if not selected or current_coverage < MIN_FEATURE_COVERAGE:
        return _insufficient_horizon(
            ticker,
            horizon,
            current_coverage,
            "Current feature coverage is below 80%.",
        )

    dataset = features[selected].copy()
    dataset["forward_return"] = forward
    dataset = dataset.dropna(subset=["forward_return"])
    if len(dataset) < MIN_TRAIN_ROWS + 60:
        return _insufficient_horizon(
            ticker,
            horizon,
            current_coverage,
            "Training history is too short.",
        )

    oos = _walk_forward(dataset, selected, horizon)
    validation = _validation_metrics(oos)
    eligible = validation.pop("eligible_models")
    current_x = features[selected].iloc[[-1]]
    training_x = dataset[selected]
    training_returns = dataset["forward_return"]
    baseline_probability = float((training_returns > 0).mean())
    model_probabilities: dict[str, float] = {"baseline": baseline_probability}
    full_fit = _fit_probability_model(training_x, training_returns, current_x)
    model_probabilities["full"] = float(full_fit.predictions[0])
    trend_columns = _trend_columns(selected)
    if trend_columns:
        trend_fit = _fit_probability_model(
            training_x[trend_columns], training_returns, current_x[trend_columns]
        )
        model_probabilities["trend"] = float(trend_fit.predictions[0])
    analog = _analog_distribution(
        training_x, training_returns, current_x.iloc[0], horizon
    )
    if analog["sample_size"] >= MIN_ANALOGS:
        model_probabilities["analog"] = float(analog["probability_up"])

    active_models = eligible or [
        name for name in ("full", "trend", "analog") if name in model_probabilities
    ]
    probability_up = float(
        np.mean([model_probabilities[name] for name in active_models])
    )
    expected_move = _implied_expected_move(cboe, horizon)
    downside_probability = _downside_probability(analog["returns"], expected_move)
    p10, p50, p90 = analog["p10"], analog["p50"], analog["p90"]
    risk_level = _forecast_risk(downside_probability, p10, expected_move)
    status = "validated" if _passes_validation(validation, analog) else "research_only"
    direction = (
        "upside_bias"
        if probability_up >= 0.58
        else "downside_bias"
        if probability_up <= 0.42
        else "neutral"
    )
    drivers = _drivers(full_fit.coefficients, training_x, current_x.iloc[0])
    confidence = _confidence(status, probability_up, validation.get("brier_skill"))
    return {
        "status": status,
        "ticker": ticker,
        "horizon_days": horizon,
        "as_of": str(features.index.max().date()),
        "model_version": MODEL_VERSION,
        "probability_up": round(probability_up, 4),
        "expected_return": _round(p50, 5),
        "p10": _round(p10, 5),
        "p50": _round(p50, 5),
        "p90": _round(p90, 5),
        "implied_expected_move": _round(expected_move, 5),
        "downside_probability": _round(downside_probability, 4),
        "risk_level": risk_level,
        "direction": direction,
        "direction_label": {
            "upside_bias": "上方向バイアス",
            "downside_bias": "下方向バイアス",
            "neutral": "中立",
        }[direction],
        "confidence": confidence,
        "sample_size": int(analog["sample_size"]),
        "oos_metrics": validation,
        "active_models": active_models,
        "feature_coverage": round(current_coverage, 3),
        "feature_count": len(selected),
        "drivers": drivers,
        "is_stale": False,
    }


def _walk_forward(
    dataset: pd.DataFrame,
    selected: list[str],
    horizon: int,
) -> dict[str, list[float]]:
    start = max(MIN_TRAIN_ROWS, len(dataset) - OOS_TARGET_ROWS)
    output: dict[str, list[float]] = {
        "actual": [],
        "actual_return": [],
        "baseline": [],
        "full": [],
        "trend": [],
        "analog": [],
        "analog_p10": [],
        "analog_p90": [],
    }
    trend_columns = _trend_columns(selected)
    for fold_start in range(start, len(dataset), REFIT_STEP):
        train_end = max(0, fold_start - horizon)
        train = dataset.iloc[:train_end]
        test = dataset.iloc[fold_start : fold_start + REFIT_STEP]
        if len(train) < MIN_TRAIN_ROWS or test.empty:
            continue
        train_x = train[selected]
        train_return = train["forward_return"]
        test_x = test[selected]
        output["actual"].extend((test["forward_return"] > 0).astype(float).tolist())
        output["actual_return"].extend(test["forward_return"].astype(float).tolist())
        output["baseline"].extend([float((train_return > 0).mean())] * len(test))
        output["full"].extend(
            _fit_probability_model(train_x, train_return, test_x).predictions.tolist()
        )
        if trend_columns:
            output["trend"].extend(
                _fit_probability_model(
                    train_x[trend_columns], train_return, test_x[trend_columns]
                ).predictions.tolist()
            )
        else:
            output["trend"].extend(output["baseline"][-len(test) :])
        analog_train, analog_test = _robust_transform(train_x, test_x)
        for _, row in analog_test.iterrows():
            analog = _analog_distribution_transformed(
                analog_train,
                train_return,
                row,
                horizon,
            )
            output["analog"].append(float(analog["probability_up"]))
            output["analog_p10"].append(float(analog["p10"]))
            output["analog_p90"].append(float(analog["p90"]))
    return output


def _validation_metrics(oos: dict[str, list[float]]) -> dict[str, Any]:
    actual = np.asarray(oos["actual"], dtype=float)
    if not len(actual):
        return {
            "oos_predictions": 0,
            "brier_skill": None,
            "log_loss": None,
            "baseline_log_loss": None,
            "ece": None,
            "interval_coverage": None,
            "eligible_models": [],
        }
    baseline = np.asarray(oos["baseline"], dtype=float)
    baseline_brier = _brier(actual, baseline)
    baseline_log_loss = _log_loss(actual, baseline)
    model_metrics: dict[str, Any] = {}
    eligible: list[str] = []
    for name in ("full", "trend", "analog"):
        predictions = np.asarray(oos[name], dtype=float)
        brier = _brier(actual, predictions)
        log_loss = _log_loss(actual, predictions)
        ece = _ece(actual, predictions)
        model_metrics[name] = {
            "brier": round(brier, 6),
            "log_loss": round(log_loss, 6),
            "ece": round(ece, 6),
        }
        if brier < baseline_brier and log_loss <= baseline_log_loss:
            eligible.append(name)
    active = eligible or ["full", "trend", "analog"]
    ensemble = np.mean([np.asarray(oos[name], dtype=float) for name in active], axis=0)
    ensemble_brier = _brier(actual, ensemble)
    lower = np.asarray(oos["analog_p10"], dtype=float)
    upper = np.asarray(oos["analog_p90"], dtype=float)
    realized = np.asarray(oos["actual_return"], dtype=float)
    interval_coverage = float(((realized >= lower) & (realized <= upper)).mean())
    return {
        "oos_predictions": int(len(actual)),
        "brier": round(ensemble_brier, 6),
        "baseline_brier": round(baseline_brier, 6),
        "brier_skill": round(1 - ensemble_brier / baseline_brier, 6)
        if baseline_brier
        else None,
        "log_loss": round(_log_loss(actual, ensemble), 6),
        "baseline_log_loss": round(baseline_log_loss, 6),
        "ece": round(_ece(actual, ensemble), 6),
        "interval_coverage": round(interval_coverage, 6),
        "model_metrics": model_metrics,
        "eligible_models": eligible,
    }


def _fit_probability_model(
    train_x: pd.DataFrame,
    train_returns: pd.Series,
    predict_x: pd.DataFrame,
) -> ProbabilityFit:
    transformed_train, transformed_predict = _robust_transform(train_x, predict_x)
    target = (train_returns > 0).astype(float).to_numpy()
    baseline = float(np.mean(target)) if len(target) else 0.5
    try:
        train_values = np.column_stack(
            [np.ones(len(transformed_train)), transformed_train.to_numpy(dtype=float)]
        )
        predict_values = np.column_stack(
            [
                np.ones(len(transformed_predict)),
                transformed_predict.to_numpy(dtype=float),
            ]
        )
        coefficients = _ridge_logistic_coefficients(train_values, target)
        predictions = np.clip(expit(predict_values @ coefficients), 0.01, 0.99)
        params = pd.Series(coefficients, index=["const", *transformed_train.columns])
        return ProbabilityFit(predictions=predictions, coefficients=params)
    except Exception:
        return ProbabilityFit(
            predictions=np.full(len(predict_x), baseline),
            coefficients=pd.Series(dtype=float),
        )


def _ridge_logistic_coefficients(
    design: np.ndarray,
    target: np.ndarray,
    *,
    ridge: float = 1.0,
    max_iterations: int = 30,
) -> np.ndarray:
    """Fit deterministic L2 logistic coefficients with bounded Newton updates."""

    coefficients = np.zeros(design.shape[1], dtype=float)
    probability = float(np.clip(target.mean(), 0.01, 0.99))
    coefficients[0] = np.log(probability / (1 - probability))
    penalty = np.eye(design.shape[1], dtype=float) * ridge
    penalty[0, 0] = 0.0
    for _ in range(max_iterations):
        fitted = expit(design @ coefficients)
        weights = np.clip(fitted * (1 - fitted), 1e-5, None)
        gradient = design.T @ (target - fitted) - penalty @ coefficients
        hessian = design.T @ (weights[:, None] * design) + penalty
        update = np.linalg.solve(hessian, gradient)
        coefficients += update
        if float(np.linalg.norm(update)) < 1e-6:
            break
    return coefficients


def _robust_transform(
    train_x: pd.DataFrame, predict_x: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    median = train_x.median()
    filled = train_x.fillna(median)
    lower = filled.quantile(0.01)
    upper = filled.quantile(0.99)
    clipped = filled.clip(lower=lower, upper=upper, axis=1)
    scale = (
        (clipped.quantile(0.75) - clipped.quantile(0.25)).replace(0, 1.0).fillna(1.0)
    )
    center = clipped.median()
    transformed_train = (clipped - center) / scale
    transformed_predict = (
        predict_x.fillna(median).clip(lower=lower, upper=upper, axis=1) - center
    ) / scale
    return transformed_train.astype(float), transformed_predict.astype(float)


def _analog_distribution(
    train_x: pd.DataFrame,
    train_returns: pd.Series,
    current_x: pd.Series,
    horizon: int,
) -> dict[str, Any]:
    transformed, current = _robust_transform(train_x, current_x.to_frame().T)
    return _analog_distribution_transformed(
        transformed,
        train_returns,
        current.iloc[0],
        horizon,
    )


def _analog_distribution_transformed(
    transformed_train: pd.DataFrame,
    train_returns: pd.Series,
    transformed_current: pd.Series,
    horizon: int,
) -> dict[str, Any]:
    distances = ((transformed_train - transformed_current) ** 2).mean(axis=1).pow(0.5)
    order = np.argsort(distances.to_numpy())
    chosen: list[int] = []
    for position in order:
        if any(abs(int(position) - prior) < max(horizon, 5) for prior in chosen):
            continue
        chosen.append(int(position))
        if len(chosen) == MAX_ANALOGS:
            break
    values = train_returns.iloc[chosen].dropna().to_numpy(dtype=float)
    if not len(values):
        values = train_returns.tail(MAX_ANALOGS).dropna().to_numpy(dtype=float)
    return {
        "sample_size": int(len(values)),
        "probability_up": float(np.mean(values > 0)) if len(values) else 0.5,
        "p10": float(np.quantile(values, 0.10)) if len(values) else 0.0,
        "p50": float(np.quantile(values, 0.50)) if len(values) else 0.0,
        "p90": float(np.quantile(values, 0.90)) if len(values) else 0.0,
        "returns": values,
    }


def _select_features(features: pd.DataFrame, horizon: int) -> list[str]:
    recent = features.tail(max(MIN_TRAIN_ROWS + OOS_TARGET_ROWS, 756))
    selected = [
        column
        for column in features.columns
        if (horizon == 20 or not column.startswith("cftc_"))
        if recent[column].notna().mean() >= MIN_FEATURE_COVERAGE
        and features[column].iloc[-1] is not None
        and pd.notna(features[column].iloc[-1])
    ]
    return selected


def _trend_columns(selected: list[str]) -> list[str]:
    return [
        column
        for column in selected
        if column.startswith("target_") or column.startswith("relative_")
    ]


def _passes_validation(validation: dict[str, Any], analog: dict[str, Any]) -> bool:
    skill = validation.get("brier_skill")
    return bool(
        validation.get("oos_predictions", 0) >= MIN_OOS_ROWS
        and skill is not None
        and skill > 0
        and validation.get("log_loss", 99) <= validation.get("baseline_log_loss", 0)
        and validation.get("ece", 1) <= 0.08
        and 0.70 <= validation.get("interval_coverage", 0) <= 0.90
        and analog.get("sample_size", 0) >= MIN_ANALOGS
    )


def _implied_expected_move(cboe: pd.DataFrame, horizon: int) -> float | None:
    symbol = "VIX1D" if horizon == 1 else "VIX9D" if horizon == 5 else "VIX"
    if symbol not in cboe:
        symbol = "VIX"
    raw = cboe.get(symbol)
    if raw is None:
        return None
    series = pd.to_numeric(raw, errors="coerce").dropna()
    if series.empty:
        return None
    return float(series.iloc[-1] / 100 * np.sqrt(horizon / 252))


def _downside_probability(
    values: np.ndarray, expected_move: float | None
) -> float | None:
    if expected_move is None or not len(values):
        return None
    return float(np.mean(values <= -expected_move))


def _forecast_risk(
    downside_probability: float | None,
    p10: float | None,
    expected_move: float | None,
) -> str:
    if downside_probability is None or p10 is None or expected_move in (None, 0):
        return "unknown"
    if downside_probability >= 0.30 or p10 <= -1.5 * expected_move:
        return "extreme"
    if downside_probability >= 0.22 or p10 <= -expected_move:
        return "high"
    if downside_probability >= 0.15:
        return "medium"
    return "low"


def _confidence(status: str, probability: float, brier_skill: Any) -> str:
    if status != "validated":
        return "unverified"
    skill = float(brier_skill or 0.0)
    distance = abs(probability - 0.5)
    if distance >= 0.15 and skill >= 0.05:
        return "high"
    if distance >= 0.08:
        return "medium"
    return "low"


def _drivers(
    coefficients: pd.Series,
    train_x: pd.DataFrame,
    current_x: pd.Series,
) -> list[dict[str, Any]]:
    if coefficients.empty:
        return []
    _, transformed = _robust_transform(train_x, current_x.to_frame().T)
    contributions = transformed.iloc[0] * coefficients.drop("const", errors="ignore")
    rows = []
    for name, _value in (
        contributions.abs().sort_values(ascending=False).head(6).items()
    ):
        contribution = float(contributions[name])
        rows.append(
            {
                "feature": name,
                "direction": "positive" if contribution >= 0 else "negative",
                "contribution": round(contribution, 4),
            }
        )
    return rows


def _target_status(horizons: dict[str, Any]) -> str:
    statuses = [item.get("status") for item in horizons.values()]
    if statuses and all(item == "validated" for item in statuses):
        return "validated"
    if any(item in {"validated", "research_only"} for item in statuses):
        return "research_only"
    return "insufficient_data"


def _target_summary(ticker: str, horizons: dict[str, Any]) -> str:
    parts = []
    for key in ("1d", "5d", "20d"):
        item = horizons.get(key) or {}
        probability = item.get("probability_up")
        value = "算出不可" if probability is None else f"上昇確率 {probability:.0%}"
        parts.append(f"{key}: {value} / {item.get('status', 'unavailable')}")
    return f"{ticker} " + "、".join(parts)


def _bundle_as_of(targets: dict[str, Any]) -> str:
    values = []
    for target in targets.values():
        for item in (target.get("horizons") or {}).values():
            if item.get("as_of"):
                values.append(str(item["as_of"]))
    return min(values) if values else ""


def _insufficient_horizon(
    ticker: str, horizon: int, coverage: float, reason: str
) -> dict[str, Any]:
    return {
        "status": "insufficient_data",
        "ticker": ticker,
        "horizon_days": horizon,
        "probability_up": None,
        "p10": None,
        "p50": None,
        "p90": None,
        "implied_expected_move": None,
        "downside_probability": None,
        "risk_level": "unknown",
        "direction": "unavailable",
        "direction_label": "検証不十分",
        "confidence": "unverified",
        "feature_coverage": round(coverage, 3),
        "quality_warnings": [reason],
    }


def _unavailable_bundle(error: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "model_version": MODEL_VERSION,
        "as_of": "",
        "fetched_at": utc_now_iso(),
        "targets": {},
        "source": "unavailable",
        "is_stale": False,
        "is_partial": True,
        "cache_status": "failed",
        "quality_warnings": [error],
        "integration_enabled": False,
    }


def _relative_series(
    frames: dict[str, pd.DataFrame], left: str, right: str
) -> pd.Series:
    joined = pd.concat(
        [
            _close(frames.get(left)).rename("left"),
            _close(frames.get(right)).rename("right"),
        ],
        axis=1,
        sort=True,
    ).dropna()
    return joined["left"] / joined["right"]


def _close(frame: pd.DataFrame | None) -> pd.Series:
    return _numeric_column(frame, "close")


def _volume(frame: pd.DataFrame | None) -> pd.Series:
    return _numeric_column(frame, "volume")


def _numeric_column(frame: pd.DataFrame | None, name: str) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    column = next((item for item in frame.columns if str(item).lower() == name), None)
    if column is None:
        return pd.Series(dtype=float)
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if isinstance(series.index, pd.DatetimeIndex):
        if series.index.tz is not None:
            series.index = series.index.tz_localize(None)
        series.index = series.index.normalize()
        series = series.loc[~series.index.duplicated(keep="last")]
    return series.sort_index()


def _normalize_index(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if isinstance(result.index, pd.DatetimeIndex):
        if result.index.tz is not None:
            result.index = result.index.tz_localize(None)
        result.index = result.index.normalize()
        result = result.loc[~result.index.duplicated(keep="last")]
    return result.sort_index()


def _rolling_z(series: pd.Series, window: int, minimum: int) -> pd.Series:
    mean = series.rolling(window, min_periods=minimum).mean()
    std = series.rolling(window, min_periods=minimum).std().replace(0, np.nan)
    return (series - mean) / std


def _safe_ratio_column(frame: pd.DataFrame, left: str, right: str) -> pd.Series:
    if left not in frame or right not in frame:
        return pd.Series(np.nan, index=frame.index)
    return frame[left] / frame[right].replace(0, np.nan)


def _brier(actual: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.mean((prediction - actual) ** 2))


def _log_loss(actual: np.ndarray, prediction: np.ndarray) -> float:
    clipped = np.clip(prediction, 0.01, 0.99)
    return float(
        -np.mean(actual * np.log(clipped) + (1 - actual) * np.log(1 - clipped))
    )


def _ece(actual: np.ndarray, prediction: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for left, right in zip(edges[:-1], edges[1:], strict=True):
        mask = (prediction >= left) & (
            prediction < right if right < 1 else prediction <= right
        )
        if mask.any():
            total += float(mask.mean()) * abs(
                float(prediction[mask].mean()) - float(actual[mask].mean())
            )
    return total


def _round(value: Any, digits: int) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(number) else round(number, digits)
