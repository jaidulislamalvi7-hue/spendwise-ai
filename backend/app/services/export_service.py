"""User-scoped data export.

Every query here is filtered by ``user.id``; a caller can only ever export their
own records. CSV is produced with the standard library so no extra dependency
is required and values are quoted safely.
"""

import csv
import io
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.lifestyle_log import LifestyleLog
from app.models.user import User

EXPENSE_COLUMNS = (
    "expense_date",
    "spent_at_utc",
    "category",
    "amount",
    "payment_method",
    "description",
    "is_restaurant_visit",
    "meal_type",
    "is_coffee_or_snack",
    "transport_mode",
    "is_shopping",
    "is_entertainment",
    "is_impulse",
    "activity_tag",
    "created_at_utc",
)

LIFESTYLE_COLUMNS = (
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
    "notes",
    "created_at_utc",
)


def _cell(value: Any) -> str:
    """Render a value for CSV without losing precision or leaking repr noise."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        # Normalise to an explicit UTC ISO-8601 string.
        return value.astimezone().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    text = str(value)
    # Neutralise spreadsheet formula injection on values that start a formula.
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


def _write_csv(columns: Iterable[str], rows: Iterable[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _cell(row.get(key)) for key in columns})
    return buffer.getvalue()


def export_expenses_csv(
    db: Session,
    user: User,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    """Return the user's expenses as CSV text.

    An empty result yields a header-only file rather than an error.
    """
    conditions = [Expense.user_id == user.id]
    if date_from is not None:
        conditions.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conditions.append(Expense.expense_date <= date_to)

    rows = db.scalars(
        select(Expense).where(*conditions).order_by(Expense.expense_date, Expense.created_at)
    ).all()

    return _write_csv(
        EXPENSE_COLUMNS,
        (
            {
                "expense_date": row.expense_date,
                "spent_at_utc": row.spent_at,
                "category": row.category,
                "amount": row.amount,
                "payment_method": row.payment_method,
                "description": row.description,
                "is_restaurant_visit": row.is_restaurant_visit,
                "meal_type": row.meal_type,
                "is_coffee_or_snack": row.is_coffee_or_snack,
                "transport_mode": row.transport_mode,
                "is_shopping": row.is_shopping,
                "is_entertainment": row.is_entertainment,
                "is_impulse": row.is_impulse,
                "activity_tag": row.activity_tag,
                "created_at_utc": row.created_at,
            }
            for row in rows
        ),
    )


def export_lifestyle_csv(
    db: Session,
    user: User,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    """Return the user's lifestyle logs as CSV text."""
    conditions = [LifestyleLog.user_id == user.id]
    if date_from is not None:
        conditions.append(LifestyleLog.log_date >= date_from)
    if date_to is not None:
        conditions.append(LifestyleLog.log_date <= date_to)

    rows = db.scalars(select(LifestyleLog).where(*conditions).order_by(LifestyleLog.log_date)).all()

    return _write_csv(
        LIFESTYLE_COLUMNS,
        (
            {
                "log_date": row.log_date,
                "sleep_hours": row.sleep_hours,
                "stress_level": row.stress_level,
                "work_mode": row.work_mode,
                "commute_mode": row.commute_mode,
                "cooked_at_home": row.cooked_at_home,
                "restaurant_visits_count": row.restaurant_visits_count,
                "coffee_snacks_count": row.coffee_snacks_count,
                "shopping_activity": row.shopping_activity,
                "social_outings_count": row.social_outings_count,
                "exercise": row.exercise,
                "notes": row.notes,
                "created_at_utc": row.created_at,
            }
            for row in rows
        ),
    )
