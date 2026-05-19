"""Optional model comparison for probabilistic stock signals."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.advisor.stock_feature_engine import FEATURE_COLUMNS


def compare_signal_models(feature_frame: pd.DataFrame) -> dict[str, Any]:
    """Compare simple ML models when scikit-learn is available.

    The app remains functional without scikit-learn; this module reports an
    unavailable status instead of adding a hard runtime dependency.
    """

    try:
        from sklearn.ensemble import (
            HistGradientBoostingClassifier,
            RandomForestClassifier,
        )
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, brier_score_loss
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except Exception as exc:  # pragma: no cover - depends on optional package
        return {
            "available": False,
            "selected_model": "Baseline",
            "reason": f"scikit-learn unavailable: {exc}",
            "models": [],
        }

    if feature_frame.empty or "forward_5d_return" not in feature_frame.columns:
        return {
            "available": False,
            "selected_model": "Baseline",
            "reason": "Insufficient feature frame.",
            "models": [],
        }

    feature_cols = [
        col
        for col in FEATURE_COLUMNS
        if col in feature_frame.columns
        and pd.api.types.is_numeric_dtype(feature_frame[col])
    ]
    data = feature_frame[feature_cols + ["forward_5d_return"]].dropna()
    if len(data) < 180 or len(feature_cols) < 5:
        return {
            "available": False,
            "selected_model": "Baseline",
            "reason": "Insufficient rows or numeric features for model comparison.",
            "models": [],
        }

    x = data[feature_cols]
    y = (data["forward_5d_return"] > 0).astype(int)
    models = {
        "Logistic Regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=500)
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=100, random_state=42, min_samples_leaf=10
        ),
        "Gradient Boosting": HistGradientBoostingClassifier(
            random_state=42, max_iter=100
        ),
    }
    splitter = TimeSeriesSplit(n_splits=3)
    results: list[dict[str, Any]] = []

    for name, model in models.items():
        accuracies: list[float] = []
        briers: list[float] = []
        for train_idx, test_idx in splitter.split(x):
            model.fit(x.iloc[train_idx], y.iloc[train_idx])
            probabilities = model.predict_proba(x.iloc[test_idx])[:, 1]
            predictions = (probabilities >= 0.5).astype(int)
            accuracies.append(float(accuracy_score(y.iloc[test_idx], predictions)))
            briers.append(float(brier_score_loss(y.iloc[test_idx], probabilities)))

        score = float(np.mean(accuracies) - np.mean(briers))
        results.append(
            {
                "model": name,
                "accuracy": round(float(np.mean(accuracies)), 4),
                "calibration_error": round(float(np.mean(briers)), 4),
                "selection_score": round(score, 4),
            }
        )

    selected = max(results, key=lambda item: item["selection_score"])
    return {
        "available": True,
        "selected_model": selected["model"],
        "reason": "Selected by time-series accuracy minus calibration error.",
        "models": results,
    }
