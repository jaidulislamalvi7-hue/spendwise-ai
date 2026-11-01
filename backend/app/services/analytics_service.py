"""Data retrieval for analytics and ML.

This service is the only bridge between the database and the pure ML package:
it loads the authenticated user's rows into pandas frames.
"""

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.lifestyle_log import LifestyleLog
from app.models.user import User


def load_transactions(
    db: Session,
    user: User,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Return the user's expenses as a DataFrame.

    Always filtered by ``user_id``; this is the isolation boundary for all
    analytics.
    """
    conditions = [Expense.user_id == user.id]
    if date_from is not None:
        conditions.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conditions.append(Expense.expense_date <= date_to)

    # Select only the columns the analytics layer consumes: loading full ORM
    # entities materialises unused fields for every row.
    statement = (
        select(
            Expense.id,
            Expense.expense_date,
            Expense.amount,
            Expense.category,
            Expense.transport_mode,
            Expense.is_restaurant_visit,
            Expense.is_coffee_or_snack,
            Expense.is_shopping,
            Expense.is_entertainment,
        )
        .where(*conditions)
        .order_by(Expense.expense_date)
    )
    rows = db.execute(statement).all()
    if not rows:
        return pd.DataFrame(
            columns=[
                "id",
                "expense_date",
                "amount",
                "category",
                "transport_mode",
                "is_restaurant_visit",
                "is_coffee_or_snack",
                "is_shopping",
                "is_entertainment",
            ]
        )
    return pd.DataFrame(
        [
            {
                "id": str(row.id),
                "expense_date": row.expense_date,
                "amount": float(row.amount),
                "category": row.category,
                "transport_mode": row.transport_mode,
                "is_restaurant_visit": row.is_restaurant_visit,
                "is_coffee_or_snack": row.is_coffee_or_snack,
                "is_shopping": row.is_shopping,
                "is_entertainment": row.is_entertainment,
            }
            for row in rows
        ]
    )


def load_lifestyle(
    db: Session,
    user: User,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Return the user's lifestyle logs as a DataFrame."""
    conditions = [LifestyleLog.user_id == user.id]
    if date_from is not None:
        conditions.append(LifestyleLog.log_date >= date_from)
    if date_to is not None:
        conditions.append(LifestyleLog.log_date <= date_to)

    rows = db.scalars(select(LifestyleLog).where(*conditions).order_by(LifestyleLog.log_date)).all()
    columns = [
        "log_date",
        "sleep_hours",
        "stress_level",
        "work_mode",
        "commute_mode",
        "cooked_at_home",
        "restaurant_visits_count",
        "coffee_snacks_count",
        "shopping_activity",
        "social_outings_count",
        "exercise",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [
            {
                "log_date": row.log_date,
                "sleep_hours": float(row.sleep_hours) if row.sleep_hours is not None else None,
                "stress_level": row.stress_level,
                "work_mode": row.work_mode,
                "commute_mode": row.commute_mode,
                "cooked_at_home": row.cooked_at_home,
                "restaurant_visits_count": row.restaurant_visits_count,
                "coffee_snacks_count": row.coffee_snacks_count,
                "shopping_activity": row.shopping_activity,
                "social_outings_count": row.social_outings_count,
                "exercise": row.exercise,
            }
            for row in rows
        ]
    )


def load_daily_series(db: Session, user: User) -> pd.DataFrame:
    """Daily total spending, ready for feature engineering."""
    from app.ml.features import build_daily_frame

    transactions = load_transactions(db, user)
    if transactions.empty:
        return pd.DataFrame({"total": pd.Series(dtype="float64")})
    return build_daily_frame(transactions["expense_date"], transactions["amount"])
