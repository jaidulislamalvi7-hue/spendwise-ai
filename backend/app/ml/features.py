"""Feature engineering for daily spending series.

Leakage rule: every historical feature for day ``t`` is computed from data at
or before ``t`` only. The target (spending on day ``t``) is never used to build
its own features. Rolling windows are shifted by one day so the current day is
excluded from its own predictors.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.ml.config import MIN_DAYS_FOR_FEATURES

WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def build_daily_frame(expense_dates: pd.Series, amounts: pd.Series) -> pd.DataFrame:
    """Aggregate transactions into a complete daily series.

    Days with no spending are included with ``total = 0`` so that gaps are
    modelled explicitly rather than silently dropped.

    Returns a frame indexed by date with column ``total``.
    """
    if len(expense_dates) == 0:
        return pd.DataFrame({"total": pd.Series(dtype="float64")})

    frame = pd.DataFrame(
        {"date": pd.to_datetime(expense_dates).dt.date, "amount": amounts.astype(float)}
    )
    daily = (
        frame.groupby("date", as_index=False)["amount"].sum().rename(columns={"amount": "total"})
    )

    full_range = pd.date_range(start=daily["date"].min(), end=daily["date"].max(), freq="D")
    calendar = pd.DataFrame({"date": [d.date() for d in full_range]})
    merged = calendar.merge(daily, on="date", how="left").fillna({"total": 0.0})
    return merged.set_index("date")


def add_calendar_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Add day-of-week, weekend flag and position features (no leakage)."""
    out = daily.copy()
    index = pd.to_datetime(out.index)
    out["dow"] = index.dayofweek
    out["is_weekend"] = (out["dow"] >= 5).astype(int)
    out["day_of_month"] = index.day
    out["is_month_end"] = index.is_month_end.astype(int)
    out["month"] = index.month
    return out


def add_historical_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Add lagged and rolling features that only look backwards.

    All rolling statistics are shifted by one day, so a row for day ``t`` can
    never see day ``t``'s own total.
    """
    out = daily.copy()
    total = out["total"]

    # Previous day (lag 1) and previous week average.
    out["lag_1"] = total.shift(1)
    out["lag_7"] = total.shift(7)
    out["prev_week_mean"] = total.shift(1).rolling(window=7, min_periods=1).mean()

    # Rolling averages over the preceding windows.
    out["rolling_mean_7"] = total.shift(1).rolling(window=7, min_periods=1).mean()
    out["rolling_mean_14"] = total.shift(1).rolling(window=14, min_periods=1).mean()
    out["rolling_mean_30"] = total.shift(1).rolling(window=30, min_periods=1).mean()
    out["rolling_std_7"] = total.shift(1).rolling(window=7, min_periods=2).std()

    return out


def add_weekday_baseline_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Add the same-weekday historical mean, using prior weeks only."""
    out = daily.copy()
    out["dow"] = pd.to_datetime(out.index).dayofweek

    # Expanding mean per weekday over previous occurrences only: groupby -> shift.
    weekly = out.groupby("dow")["total"].transform(
        lambda s: s.shift(1).expanding(min_periods=1).mean()
    )
    out["same_weekday_mean"] = weekly
    return out


def add_category_features(
    daily: pd.DataFrame, transactions: pd.DataFrame, top_n: int = 5
) -> pd.DataFrame:
    """Add per-category daily spending shares and prior-day category totals.

    Category columns are lagged so they cannot leak the target day.
    """
    out = daily.copy()
    if transactions.empty:
        return out

    transactions = transactions.copy()
    transactions["expense_date"] = pd.to_datetime(transactions["expense_date"]).dt.date
    top_categories = (
        transactions.groupby("category")["amount"].sum().sort_values(ascending=False).head(top_n)
    ).index

    for category in top_categories:
        subset = transactions[transactions["category"] == category]
        per_day = subset.groupby("expense_date")["amount"].sum()
        column = f"cat_{category}"
        # Bind per_day as a default argument; otherwise the closure would read the
        # loop variable at call time and the last category would win (B023).
        series = out.index.map(lambda d, values=per_day: float(values.get(d, 0.0)))
        # Lag by one day so the feature uses only prior-day category spending.
        out[column] = pd.Series(series, index=out.index).shift(1)

    return out


def add_lifestyle_features(
    daily: pd.DataFrame, lifestyle: pd.DataFrame, lag_days: int = 1
) -> pd.DataFrame:
    """Merge lifestyle indicators, lagged so they cannot leak the target day.

    By default the *previous* day's lifestyle values are attached to each day,
    which is what a predictor may legitimately use. Pass ``lag_days=0`` only for
    descriptive analysis (e.g. correlation), never for prediction input.
    """
    out = daily.copy()
    if lifestyle.empty:
        return out

    lifestyle = lifestyle.copy()
    lifestyle["log_date"] = pd.to_datetime(lifestyle["log_date"]).dt.date
    lifestyle = lifestyle.set_index("log_date")
    joins = [
        c
        for c in (
            "sleep_hours",
            "stress_level",
            "restaurant_visits_count",
            "coffee_snacks_count",
            "social_outings_count",
        )
        if c in lifestyle.columns
    ]
    for column in joins:
        # Bind column as a default argument so each closure keeps its own key
        # instead of reading the loop variable after it changes (B023).
        values = pd.Series(
            out.index.map(lambda d, key=column: lifestyle[key].get(d, np.nan)),
            index=out.index,
        )
        out[column] = values.shift(lag_days) if lag_days else values
    return out


def build_feature_matrix(daily: pd.DataFrame) -> pd.DataFrame:
    """Assemble the full feature frame from a daily series."""
    features = add_calendar_features(daily)
    features = add_historical_features(features)
    features = add_weekday_baseline_features(features)
    return features


def handle_missing_values(features: pd.DataFrame) -> pd.DataFrame:
    """Fill missing feature values without leaking future information.

    Early rows have no history; they are filled with the first available
    historical mean, falling back to 0.0 when the series is too short.
    """
    out = features.copy()
    feature_columns = [c for c in out.columns if c != "total"]
    for column in feature_columns:
        out[column] = out[column].astype(float)
    if out.empty:
        return out
    # Forward-fill uses only past values; then fill any remaining leading gaps.
    out[feature_columns] = out[feature_columns].ffill()
    out[feature_columns] = out[feature_columns].fillna(0.0)
    return out


def prediction_feature_columns() -> list[str]:
    """Columns used as model inputs (never the target)."""
    return [
        "dow",
        "is_weekend",
        "day_of_month",
        "is_month_end",
        "lag_1",
        "lag_7",
        "prev_week_mean",
        "rolling_mean_7",
        "rolling_mean_14",
        "rolling_mean_30",
        "rolling_std_7",
        "same_weekday_mean",
    ]


def is_sufficient_for_features(daily: pd.DataFrame) -> bool:
    """Return True when there is enough history to build meaningful features."""
    return len(daily) >= MIN_DAYS_FOR_FEATURES


def date_range_days(start: date, end: date) -> list[date]:
    """Return every date between ``start`` and ``end`` inclusive."""
    span = (end - start).days
    return [start + timedelta(days=offset) for offset in range(span + 1)]
