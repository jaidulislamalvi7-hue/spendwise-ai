"""Expense prediction: statistical baselines first, models only when justified.

Rules enforced here:
- time-ordered evaluation only (never random splits);
- baselines are always computed and are the default output;
- a regression model is used only when it beats the baseline on held-out data
  with a sufficient number of evaluation days;
- insufficient history yields an explicit insufficient-data response.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from app.ml.config import (
    MIN_DAYS_FOR_BASELINE,
    MIN_DAYS_FOR_MODEL,
    MIN_EVALUATION_DAYS,
)
from app.ml.features import build_feature_matrix, handle_missing_values, prediction_feature_columns


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """MAE and RMSE for a set of predictions."""
    if len(actual) == 0:
        return {"mae": 0.0, "rmse": 0.0}
    errors = actual - predicted
    return {
        "mae": round(float(np.mean(np.abs(errors))), 4),
        "rmse": round(float(np.sqrt(np.mean(errors**2))), 4),
    }


def historical_average_baseline(total: pd.Series, start_index: int) -> np.ndarray:
    """Predict each day with the mean of all *prior* days (expanding mean)."""
    prior_means: list[float] = []
    for position in range(start_index, len(total)):
        history = total.iloc[:position]
        prior_means.append(float(history.mean()) if len(history) else 0.0)
    return np.array(prior_means)


def same_weekday_baseline(daily: pd.DataFrame, start_index: int) -> np.ndarray:
    """Predict each day with the mean of the same weekday on earlier days."""
    dows = pd.to_datetime(daily.index).dayofweek
    total = daily["total"].to_numpy(dtype=float)
    predictions: list[float] = []
    for position in range(start_index, len(total)):
        dow = dows[position]
        history_positions = [i for i in range(position) if dows[i] == dow]
        if history_positions:
            predictions.append(float(np.mean(total[history_positions])))
        elif position > 0:
            predictions.append(float(np.mean(total[:position])))
        else:
            predictions.append(0.0)
    return np.array(predictions)


def _regression_predictions(features: pd.DataFrame, start_index: int) -> np.ndarray | None:
    """Fit on rows before ``start_index`` and predict from ``start_index`` onward.

    Returns None whenever the model cannot produce usable predictions (too few
    training rows, a constant target, or a fit/predict failure). Callers must
    fall back to a baseline in that case.
    """
    columns = [c for c in prediction_feature_columns() if c in features.columns]
    if not columns or start_index < 2:
        return None
    train = features.iloc[:start_index]
    test = features.iloc[start_index:]
    if len(test) == 0 or len(train) < 2:
        return None
    # A constant target carries no learnable signal.
    if train["total"].nunique() < 2:
        return None
    model = GradientBoostingRegressor(random_state=42)
    try:
        model.fit(train[columns], train["total"])
        predictions = np.asarray(model.predict(test[columns]), dtype=float)
    except (ValueError, TypeError):
        return None
    if predictions.size == 0 or not np.all(np.isfinite(predictions)):
        return None
    return predictions


def evaluate_and_predict(daily: pd.DataFrame) -> dict[str, Any]:
    """Evaluate baselines (and optionally a model) on a time-ordered holdout.

    The final ``MIN_EVALUATION_DAYS`` days are held out for evaluation; nothing
    before that window is ever evaluated against.
    """
    days = len(daily)
    if days < MIN_DAYS_FOR_BASELINE:
        return {
            "status": "insufficient_data",
            "days_available": days,
            "min_days_required": MIN_DAYS_FOR_BASELINE,
            "message": (
                "Not enough recorded days to produce a prediction. Keep logging "
                "expenses and this will become available."
            ),
        }

    features = handle_missing_values(build_feature_matrix(daily))
    holdout = min(MIN_EVALUATION_DAYS, max(1, days // 3))
    start_index = days - holdout
    actual = features["total"].to_numpy(dtype=float)[start_index:]

    average_predictions = historical_average_baseline(features["total"], start_index)
    weekday_predictions = same_weekday_baseline(features, start_index)

    candidates: dict[str, dict[str, float]] = {
        "historical_average": _metrics(actual, average_predictions),
        "same_weekday": _metrics(actual, weekday_predictions),
    }

    best_baseline_name = min(candidates, key=lambda name: candidates[name]["mae"])
    best_baseline = candidates[best_baseline_name]

    result: dict[str, Any] = {
        "status": "ok",
        "days_used": days,
        "holdout_days": holdout,
        "evaluation": {
            "criterion": "mean absolute error (lower is better)",
            "baselines": candidates,
            "best_baseline": best_baseline_name,
        },
        "method": best_baseline_name,
        "method_type": "statistical_baseline",
        "sample_size": days,
    }

    model_predictions = None
    if days >= MIN_DAYS_FOR_MODEL and holdout >= MIN_EVALUATION_DAYS:
        model_predictions = _regression_predictions(features, start_index)
        if model_predictions is None:
            result["model_skipped_reason"] = (
                "The model could not be trained or produced no usable predictions "
                "(for example constant spending), so a baseline is reported."
            )
        else:
            model_metrics = _metrics(actual, model_predictions)
            result["evaluation"]["model"] = model_metrics
            beats = (
                model_metrics["mae"] < best_baseline["mae"]
                and model_metrics["rmse"] < best_baseline["rmse"]
            )
            if beats:
                result["method"] = "gradient_boosting"
                result["method_type"] = "model"
            else:
                result["model_rejected_reason"] = (
                    "The model did not beat the baseline on held-out days, so the "
                    "baseline is reported instead."
                )
    else:
        result["model_skipped_reason"] = (
            "Insufficient history or evaluation window to justify a trained model."
        )

    # Next-day forecast. A baseline always exists, so this value is always set.
    if result["method_type"] == "model" and model_predictions is not None:
        next_day = float(model_predictions[-1])
        result["forecast_source"] = "model"
    elif best_baseline_name == "same_weekday" and len(weekday_predictions):
        next_day = float(weekday_predictions[-1])
        result["forecast_source"] = "same_weekday_baseline"
    else:
        next_day = float(features["total"].mean())
        result["forecast_source"] = "historical_average_baseline"

    # Guard against an undefined value (e.g. an entirely empty history).
    if not np.isfinite(next_day):
        next_day = 0.0
        result["forecast_source"] = "fallback_zero"

    result["next_day_forecast"] = round(next_day, 2)
    result["weekly_forecast"] = round(next_day * 7, 2)
    result["caveat"] = (
        "Forecasts extrapolate past patterns. They carry error and are not guarantees; "
        "the reported error figures show how large that error was historically."
    )
    return result


def feature_importance(features: pd.DataFrame) -> dict[str, Any]:
    """Rank model features by how much a fitted model relies on them."""
    columns = [c for c in prediction_feature_columns() if c in features.columns]
    if len(features) < MIN_DAYS_FOR_MODEL or not columns:
        return {
            "status": "insufficient_data",
            "min_days_required": MIN_DAYS_FOR_MODEL,
            "features": [],
            "caveat": None,
        }
    frame = features.copy()
    if frame["total"].nunique() < 2:
        return {"status": "insufficient_variation", "features": [], "caveat": None}

    model = GradientBoostingRegressor(random_state=42)
    try:
        model.fit(frame[columns], frame["total"])
    except (ValueError, TypeError):
        return {"status": "insufficient_data", "features": [], "caveat": None}

    weights = sorted(
        (
            {"feature": name, "importance": round(float(value), 4)}
            for name, value in zip(columns, model.feature_importances_, strict=False)
        ),
        key=lambda item: item["importance"],
        reverse=True,
    )
    return {
        "status": "ok",
        "features": weights,
        "caveat": (
            "Feature importance describes how much this model used each input, not a "
            "causal effect on spending."
        ),
    }
