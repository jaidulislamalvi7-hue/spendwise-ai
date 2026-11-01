"""Descriptive analytics: totals, breakdowns, trends and behaviour summaries.

These are pure calculations over a pandas frame; no database or HTTP access.
"""

from itertools import pairwise

import numpy as np
import pandas as pd

from app.ml.features import WEEKDAY_NAMES, build_daily_frame


def _daily(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame({"total": pd.Series(dtype="float64")})
    return build_daily_frame(transactions["expense_date"], transactions["amount"])


def summary(transactions: pd.DataFrame) -> dict:
    """Overall totals for the user's recorded transactions."""
    if transactions.empty:
        return {
            "transaction_count": 0,
            "days_recorded": 0,
            "total_spend": 0.0,
            "average_per_day": 0.0,
            "average_per_transaction": 0.0,
            "median_transaction": 0.0,
            "largest_transaction": 0.0,
            "date_from": None,
            "date_to": None,
        }

    daily = _daily(transactions)
    amounts = transactions["amount"].astype(float)
    return {
        "transaction_count": int(len(transactions)),
        "days_recorded": int(len(daily)),
        "total_spend": round(float(amounts.sum()), 2),
        "average_per_day": round(float(daily["total"].mean()), 2),
        "average_per_transaction": round(float(amounts.mean()), 2),
        "median_transaction": round(float(amounts.median()), 2),
        "largest_transaction": round(float(amounts.max()), 2),
        "date_from": str(daily.index.min()),
        "date_to": str(daily.index.max()),
    }


def category_breakdown(transactions: pd.DataFrame) -> list[dict]:
    """Category totals with their share of overall spend."""
    if transactions.empty:
        return []

    grouped = (
        transactions.assign(amount=transactions["amount"].astype(float))
        .groupby("category")
        .agg(total=("amount", "sum"), count=("amount", "size"), average=("amount", "mean"))
        .sort_values("total", ascending=False)
    )
    overall = float(grouped["total"].sum()) or 1.0
    return [
        {
            "category": category,
            "total": round(float(row["total"]), 2),
            "transaction_count": int(row["count"]),
            "average": round(float(row["average"]), 2),
            "percentage": round(float(row["total"]) / overall * 100, 2),
        }
        for category, row in grouped.iterrows()
    ]


def _period_series(daily: pd.DataFrame, freq: str) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame(columns=["period", "total"])
    index = pd.to_datetime(daily.index)
    series = pd.Series(daily["total"].to_numpy(), index=index)
    resampled = series.resample(freq).sum()
    return pd.DataFrame({"period": resampled.index.astype(str), "total": resampled.to_numpy()})


def trends(transactions: pd.DataFrame) -> dict:
    """Daily, weekly and monthly totals plus a simple direction indicator."""
    daily = _daily(transactions)
    if daily.empty:
        return {"daily": [], "weekly": [], "monthly": [], "trend_direction": "insufficient_data"}

    daily_frame = pd.DataFrame(
        {"period": [str(d) for d in daily.index], "total": daily["total"].round(2).tolist()}
    )
    weekly = _period_series(daily, "W-MON")
    monthly = _period_series(daily, "MS")
    for frame in (weekly, monthly):
        frame["total"] = frame["total"].round(2)

    return {
        "daily": daily_frame.to_dict(orient="records"),
        "weekly": weekly.to_dict(orient="records"),
        "monthly": monthly.to_dict(orient="records"),
        "trend_direction": trend_direction(daily["total"]),
    }


def trend_direction(daily_totals: pd.Series) -> str:
    """Compare the recent half of the series with the earlier half.

    A simple descriptive comparison, not a statistical test.

    Returns one of ``increasing``, ``decreasing``, ``flat`` or
    ``insufficient_data``. A change of more than 10% is treated as a direction.
    """
    values = daily_totals.to_numpy()
    if len(values) < 4:
        return "insufficient_data"
    midpoint = len(values) // 2
    earlier = float(np.mean(values[:midpoint]))
    later = float(np.mean(values[midpoint:]))
    if earlier == 0:
        return "increasing" if later > 0 else "flat"
    change = (later - earlier) / earlier
    if change > 0.1:
        return "increasing"
    if change < -0.1:
        return "decreasing"
    return "flat"


def weekday_vs_weekend(transactions: pd.DataFrame) -> dict:
    """Compare spending on weekdays versus weekends."""
    daily = _daily(transactions)
    if daily.empty:
        return {
            "weekday_average": 0.0,
            "weekend_average": 0.0,
            "weekday_days": 0,
            "weekend_days": 0,
            "difference": 0.0,
        }
    dows = pd.to_datetime(daily.index).dayofweek
    weekend_mask = dows >= 5
    weekday_values = daily["total"][~weekend_mask]
    weekend_values = daily["total"][weekend_mask]
    weekday_avg = float(weekday_values.mean()) if len(weekday_values) else 0.0
    weekend_avg = float(weekend_values.mean()) if len(weekend_values) else 0.0
    return {
        "weekday_average": round(weekday_avg, 2),
        "weekend_average": round(weekend_avg, 2),
        "weekday_days": int(len(weekday_values)),
        "weekend_days": int(len(weekend_values)),
        "difference": round(weekend_avg - weekday_avg, 2),
    }


def dow_profile(transactions: pd.DataFrame) -> list[dict]:
    """Average spending per day of week."""
    daily = _daily(transactions)
    if daily.empty:
        return []
    dows = pd.to_datetime(daily.index).dayofweek
    frame = pd.DataFrame({"dow": dows, "total": daily["total"].to_numpy()})
    grouped = frame.groupby("dow")["total"].agg(["mean", "size"])
    return [
        {
            "weekday": WEEKDAY_NAMES[int(dow)],
            "average": round(float(row["mean"]), 2),
            "days": int(row["size"]),
        }
        for dow, row in grouped.iterrows()
    ]


def behaviour_summary(transactions: pd.DataFrame) -> dict:
    """Descriptive behaviour measures (all stated plainly, no judgements)."""
    if transactions.empty:
        return {
            "no_spend_days": 0,
            "average_transactions_per_day": 0.0,
            "most_frequent_category": None,
            "small_transaction_share": 0.0,
            "largest_day": None,
        }

    daily = _daily(transactions)
    amounts = transactions["amount"].astype(float)
    counts = transactions.groupby("expense_date").size()
    counts_over_day = counts.reindex(daily.index).fillna(0)
    category_counts = transactions["category"].value_counts()
    small_share = float((amounts < amounts.median()).mean() * 100) if len(amounts) else 0.0
    largest_day = daily["total"].idxmax()
    return {
        "no_spend_days": int((daily["total"] == 0).sum()),
        "average_transactions_per_day": round(float(counts_over_day.mean()), 2),
        "most_frequent_category": str(category_counts.index[0]) if len(category_counts) else None,
        "small_transaction_share": round(small_share, 2),
        "largest_day": {"date": str(largest_day), "total": round(float(daily["total"].max()), 2)},
    }


def consecutive_gaps(daily_totals: pd.Series) -> int:
    """Number of zero-spend days (useful as a descriptive signal)."""
    return int((daily_totals == 0).sum())


def pairwise_week_averages(daily_totals: pd.Series) -> float:
    """Mean absolute change between consecutive days (descriptive volatility)."""
    values = daily_totals.to_numpy(dtype=float)
    if len(values) < 2:
        return 0.0
    changes = [abs(b - a) for a, b in pairwise(values)]
    return float(np.mean(changes))
