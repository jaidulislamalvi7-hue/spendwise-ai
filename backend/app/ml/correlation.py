"""Cautious correlation analysis between lifestyle factors and spending.

Rules enforced here:
- results are suppressed below a minimum number of paired observations;
- sample size is always reported;
- strength is described in plain-language bands;
- a causation caveat accompanies every result.

Implemented with numpy only (no scipy dependency): Pearson r for linear
association, and its rank-based equivalent on ranked data for ordinal measures.
"""

from typing import Any

import numpy as np
import pandas as pd

from app.ml.config import (
    CORRELATION_CAUTION_PAIRS,
    CORRELATION_CAVEAT,
    CORRELATION_MODERATE,
    CORRELATION_STRONG,
    CORRELATION_WEAK,
    MIN_CORRELATION_PAIRS,
)

NUMERIC_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("sleep_hours", "sleep_hours_vs_daily_spend", "pearson"),
    ("stress_level", "stress_vs_daily_spend", "spearman"),
    ("restaurant_visits_count", "restaurant_visits_vs_daily_spend", "spearman"),
    ("coffee_snacks_count", "coffee_snacks_vs_daily_spend", "spearman"),
    ("social_outings_count", "social_outings_vs_daily_spend", "spearman"),
)
BINARY_PAIRS: tuple[tuple[str, str], ...] = (
    ("is_weekend", "weekend_vs_daily_spend"),
    ("cooked_at_home", "cooked_at_home_vs_daily_spend"),
    ("exercise", "exercise_vs_daily_spend"),
)


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation, returning nan for degenerate input."""
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman correlation via Pearson on ranks (ties averaged by default)."""
    ranks_a = pd.Series(a).rank().to_numpy()
    ranks_b = pd.Series(b).rank().to_numpy()
    return pearson(ranks_a, ranks_b)


def strength_label(coefficient: float) -> str:
    """Describe |r| in cautious bands."""
    magnitude = abs(coefficient)
    if magnitude < CORRELATION_WEAK:
        return "weak"
    if magnitude < CORRELATION_MODERATE:
        return "moderate"
    if magnitude < CORRELATION_STRONG:
        return "fairly strong"
    return "strong"


def _direction(coefficient: float) -> str:
    if coefficient > 0:
        return "positive"
    if coefficient < 0:
        return "negative"
    return "none"


def correlate_pair(series_a: pd.Series, series_b: pd.Series, method: str) -> tuple[float, int]:
    """Return (coefficient, pair_count) for complete pairs.

    Only complete pairs are used; missing lifestyle entries reduce the sample
    rather than being imputed, so reported N is honest.
    """
    frame = pd.DataFrame({"a": series_a, "b": series_b}).dropna()
    pairs = len(frame)
    if pairs < 2:
        return float("nan"), pairs
    a = frame["a"].to_numpy(dtype=float)
    b = frame["b"].to_numpy(dtype=float)
    coefficient = spearman(a, b) if method == "spearman" else pearson(a, b)
    return coefficient, pairs


def _result(
    metric: str,
    method: str,
    coefficient: float,
    pairs: int,
    sufficient: bool,
) -> dict[str, Any]:
    return {
        "metric": metric,
        "method": method,
        "coefficient": None if not sufficient else round(float(coefficient), 4),
        "sample_size": int(pairs),
        "sufficient": sufficient,
        "strength": None if not sufficient else strength_label(coefficient),
        "direction": None if not sufficient else _direction(coefficient),
        "caution": bool(pairs < CORRELATION_CAUTION_PAIRS),
        "caveat": CORRELATION_CAVEAT,
        "note": None if sufficient else "insufficient paired observations",
    }


def analyse(daily_with_lifestyle: pd.DataFrame) -> dict[str, Any]:
    """Correlate lifestyle factors with daily spending."""
    results: list[dict[str, Any]] = []

    for column, metric, method in NUMERIC_PAIRS:
        if column not in daily_with_lifestyle.columns:
            continue
        coefficient, pairs = correlate_pair(
            daily_with_lifestyle[column], daily_with_lifestyle["total"], method
        )
        sufficient = pairs >= MIN_CORRELATION_PAIRS and not np.isnan(coefficient)
        results.append(_result(metric, method, coefficient, pairs, sufficient))

    for column, metric in BINARY_PAIRS:
        if column not in daily_with_lifestyle.columns:
            continue
        coefficient, pairs = correlate_pair(
            daily_with_lifestyle[column].astype(float), daily_with_lifestyle["total"], "pearson"
        )
        sufficient = pairs >= MIN_CORRELATION_PAIRS and not np.isnan(coefficient)
        results.append(_result(metric, "point_biserial", coefficient, pairs, sufficient))

    return {
        "results": results,
        "min_pairs_required": MIN_CORRELATION_PAIRS,
        "caution_below_pairs": CORRELATION_CAUTION_PAIRS,
        "caveat": CORRELATION_CAVEAT,
    }
