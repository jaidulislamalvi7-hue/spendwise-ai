"""Unusual-expense detection: robust statistics first, Isolation Forest optional."""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.ml.config import (
    ANOMALY_CAVEAT,
    ANOMALY_MAD_THRESHOLD,
    ANOMALY_ZERO_MAD_MARGIN,
    MIN_ANOMALY_HISTORY,
)


def median_absolute_deviation(values: np.ndarray) -> float:
    """Median absolute deviation from the median."""
    if len(values) == 0:
        return 0.0
    median = float(np.median(values))
    return float(np.median(np.abs(values - median)))


def _category_series(transactions: pd.DataFrame, category: str) -> np.ndarray:
    subset = transactions[transactions["category"] == category]
    return subset["amount"].astype(float).to_numpy()


def detect_robust(transactions: pd.DataFrame) -> dict[str, Any]:
    """Flag transactions that are unusual relative to their own category.

    Uses median + MAD within each category. MAD is scaled by 1.4826 so it is
    comparable to a standard deviation for normal-ish data.
    """
    base = {"method": "median_mad", "caveat": ANOMALY_CAVEAT, "threshold": ANOMALY_MAD_THRESHOLD}
    if transactions.empty:
        return {**base, "status": "insufficient_data", "flagged": [], "checked": 0}

    flags: list[dict[str, Any]] = []
    checked = 0
    for category in transactions["category"].unique():
        amounts = _category_series(transactions, category)
        if len(amounts) < MIN_ANOMALY_HISTORY:
            continue
        checked += int(len(amounts))
        median = float(np.median(amounts))
        mad = median_absolute_deviation(amounts)
        scaled = mad * 1.4826

        if scaled == 0:
            # Most values are identical, so MAD is 0 and a z-score is undefined.
            # Flag values that differ from the median by a meaningful relative
            # margin instead of silently skipping the whole category.
            subset = transactions[transactions["category"] == category]
            for _, row in subset.iterrows():
                amount = float(row["amount"])
                if amount <= median:
                    continue
                margin = (amount - median) / median if median else float("inf")
                if margin >= ANOMALY_ZERO_MAD_MARGIN:
                    flags.append(
                        {
                            "id": str(row.get("id", "")),
                            "expense_date": str(row["expense_date"]),
                            "category": category,
                            "amount": round(amount, 2),
                            "category_median": round(median, 2),
                            "robust_z": None,
                            "reason": (
                                f"{amount:.2f} is far above the usual {category} spend "
                                f"(median {median:.2f})."
                            ),
                        }
                    )
            continue

        subset = transactions[transactions["category"] == category]
        for _, row in subset.iterrows():
            amount = float(row["amount"])
            z_score = (amount - median) / scaled
            if z_score > ANOMALY_MAD_THRESHOLD:
                flags.append(
                    {
                        "id": str(row.get("id", "")),
                        "expense_date": str(row["expense_date"]),
                        "category": category,
                        "amount": round(amount, 2),
                        "category_median": round(median, 2),
                        "robust_z": round(float(z_score), 2),
                        "reason": (
                            f"{amount:.2f} is well above the usual {category} spend "
                            f"(median {median:.2f})."
                        ),
                    }
                )

    # Descending by robust z-score; records without one (zero-spread categories
    # cannot produce a z-score) sort after every scored record.
    flags.sort(
        key=lambda item: (
            item["robust_z"] is None,
            -(item["robust_z"] if item["robust_z"] is not None else 0.0),
        )
    )
    return {**base, "status": "ok", "checked": checked, "flagged": flags}


def detect_isolation_forest(transactions: pd.DataFrame) -> dict[str, Any]:
    """Optional comparison method operating on log amount and category code."""
    base = {"method": "isolation_forest", "caveat": ANOMALY_CAVEAT}
    if len(transactions) < MIN_ANOMALY_HISTORY * 2:
        return {**base, "status": "insufficient_data", "flagged": []}

    frame = transactions.copy()
    frame["log_amount"] = np.log1p(frame["amount"].astype(float))
    frame["category_code"] = frame["category"].astype("category").cat.codes
    values = frame[["log_amount", "category_code"]].to_numpy(dtype=float)
    model = IsolationForest(random_state=42, contamination="auto")
    predictions = model.fit_predict(values)

    flagged = []
    for (_, row), label in zip(frame.iterrows(), predictions, strict=False):
        if label == -1:
            flagged.append(
                {
                    "id": str(row.get("id", "")),
                    "expense_date": str(row["expense_date"]),
                    "category": row["category"],
                    "amount": round(float(row["amount"]), 2),
                    "reason": "Flagged as an outlier in amount/category space.",
                }
            )
    return {**base, "status": "ok", "checked": int(len(frame)), "flagged": flagged}


def detect(transactions: pd.DataFrame, include_isolation_forest: bool = False) -> dict[str, Any]:
    """Run robust detection and optionally compare with Isolation Forest."""
    primary = detect_robust(transactions)
    payload: dict[str, Any] = {"primary": primary}
    if include_isolation_forest:
        payload["comparison"] = detect_isolation_forest(transactions)
    return payload
