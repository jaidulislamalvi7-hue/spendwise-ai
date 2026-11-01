"""Clustering of spending *days* (never people).

Days are grouped by their own spending characteristics. Labels are descriptive,
derived from the data, and deliberately avoid moral language.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from app.ml.config import MIN_CLUSTER_DAYS

CLUSTER_FEATURES = ("total", "transaction_count", "is_weekend", "max_transaction")
CANDIDATE_K = (2, 3, 4)


def _feature_frame(transactions: pd.DataFrame) -> pd.DataFrame:
    """Build one row per day with the clustering features."""
    frame = transactions.copy()
    frame["amount"] = frame["amount"].astype(float)
    frame["expense_date"] = pd.to_datetime(frame["expense_date"]).dt.date
    grouped = frame.groupby("expense_date").agg(
        total=("amount", "sum"),
        transaction_count=("amount", "size"),
        max_transaction=("amount", "max"),
    )
    index = pd.to_datetime(grouped.index)
    grouped["is_weekend"] = (index.dayofweek >= 5).astype(float)
    return grouped


def max_usable_k(n_samples: int) -> int:
    """Largest k that is meaningful for ``n_samples`` rows.

    Silhouette scoring requires at least two clusters and at least one sample
    outside the current cluster, so k must stay below the sample count.
    """
    return max(0, min(max(CANDIDATE_K), n_samples - 1))


def choose_k(scaled: np.ndarray, max_k: int) -> tuple[int, float]:
    """Pick k by silhouette score, restricted to interpretable small values.

    Returns ``(0, -1.0)`` when no valid k can be evaluated, including the case
    where every row has identical features (clustering is meaningless then).
    """
    n_samples = len(scaled)
    if n_samples < 3 or max_k < 2:
        return 0, -1.0
    # Identical rows cannot be separated into distinct groups.
    if np.unique(scaled, axis=0).shape[0] < 2:
        return 0, -1.0

    best_k, best_score = 0, -1.0
    upper = min(max_k, n_samples - 1)
    for k in CANDIDATE_K:
        if k > upper:
            continue
        try:
            labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(scaled)
            if len(set(labels)) < 2:
                continue
            score = float(silhouette_score(scaled, labels))
        except (ValueError, TypeError):
            continue
        if score > best_score:
            best_k, best_score = k, score
    return best_k, best_score


def _describe(centroids: dict[str, float], overall_total: float) -> tuple[str, list[str]]:
    """Build a neutral, descriptive label from relative spend level."""
    average = centroids["total"]
    ratio = average / overall_total if overall_total else 1.0
    if ratio >= 1.5:
        label = "higher-spend days"
    elif ratio <= 0.5:
        label = "lower-spend days"
    else:
        label = "typical-spend days"

    traits: list[str] = []
    if centroids["is_weekend"] >= 0.6:
        traits.append("mostly weekend")
    elif centroids["is_weekend"] <= 0.2:
        traits.append("mostly weekdays")
    if centroids["transaction_count"] >= 3:
        traits.append("many transactions")
    elif centroids["transaction_count"] <= 1:
        traits.append("few transactions")
    return label, traits


def cluster_days(transactions: pd.DataFrame) -> dict[str, Any]:
    """Cluster a user's spending days and describe each group."""
    base = {
        "method": "kmeans",
        "caveat": (
            "Groups are statistical groupings of this user's own days. They are "
            "descriptions of spending patterns, not judgements about the person."
        ),
    }
    if transactions.empty:
        return {**base, "status": "insufficient_data", "days": 0, "clusters": []}

    features = _feature_frame(transactions)
    if len(features) < MIN_CLUSTER_DAYS:
        return {
            **base,
            "status": "insufficient_data",
            "days": int(len(features)),
            "min_days_required": MIN_CLUSTER_DAYS,
            "clusters": [],
        }

    values = features[list(CLUSTER_FEATURES)].to_numpy(dtype=float)
    scaled = StandardScaler().fit_transform(values)

    best_k, score = choose_k(scaled, max_k=max_usable_k(len(features)))
    if best_k == 0:
        return {
            **base,
            "status": "insufficient_variation",
            "days": int(len(features)),
            "clusters": [],
            "note": (
                "These days are too similar to form meaningful groups, so no clusters are reported."
            ),
        }

    model = KMeans(n_clusters=best_k, n_init=10, random_state=42)
    labels = model.fit_predict(scaled)
    features = features.assign(cluster=labels)

    overall_total = float(features["total"].mean())
    clusters: list[dict[str, Any]] = []
    for cluster_id in sorted(set(labels)):
        subset = features[features["cluster"] == cluster_id]
        centroids = {
            "total": float(subset["total"].mean()),
            "transaction_count": float(subset["transaction_count"].mean()),
            "is_weekend": float(subset["is_weekend"].mean()),
            "max_transaction": float(subset["max_transaction"].mean()),
        }
        label, traits = _describe(centroids, overall_total)
        clusters.append(
            {
                "cluster_id": int(cluster_id),
                "label": label,
                "traits": traits,
                "days": int(len(subset)),
                "average_total": round(centroids["total"], 2),
                "average_transactions": round(centroids["transaction_count"], 2),
                "weekend_share": round(centroids["is_weekend"], 2),
                "average_largest_transaction": round(centroids["max_transaction"], 2),
            }
        )

    return {
        **base,
        "status": "ok",
        "days": int(len(features)),
        "k": int(best_k),
        "silhouette": round(float(score), 4),
        "silhouette_note": (
            "Silhouette measures separation between groups; values near 0 mean the "
            "groups are weak and should not be over-interpreted."
        ),
        "clusters": clusters,
    }


def silhouette_of(labels: np.ndarray, values: np.ndarray) -> float:
    """Expose silhouette for tests."""
    if len(set(labels)) < 2:
        return -1.0
    return float(silhouette_score(values, labels))
