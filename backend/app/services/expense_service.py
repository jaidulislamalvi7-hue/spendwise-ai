"""Expense service: all reads and writes are scoped to the owning user."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.user import User
from app.schemas.common import ExpenseDateError, resolve_expense_moment
from app.schemas.expense import ExpenseCreate, ExpenseUpdate


class ExpenseNotFoundError(Exception):
    """Raised when an expense does not exist for this user."""


class ExpenseDateConflictError(Exception):
    """Raised when supplied date and timestamp describe different days."""


def _resolve_dates(
    user: User, spent_at: datetime | None, expense_date: date | None
) -> tuple[datetime, date]:
    """Return (spent_at, user-local expense_date) via the shared contract.

    ``spent_at`` is normalised to UTC; the date is always derived in the user's
    IANA timezone, never the server's.
    """
    try:
        return resolve_expense_moment(
            timezone=user.timezone,
            spent_at=spent_at,
            expense_date=expense_date,
            fallback_spent_at=datetime.now(tz=UTC)
            if spent_at is None and expense_date is None
            else None,
        )
    except ExpenseDateError as exc:
        raise ExpenseDateConflictError(str(exc)) from exc


def create_expense(db: Session, user: User, payload: ExpenseCreate) -> Expense:
    """Create an expense owned by ``user``."""
    spent_at, expense_date = _resolve_dates(user, payload.spent_at, payload.expense_date)
    expense = Expense(
        user_id=user.id,
        amount=payload.amount,
        spent_at=spent_at,
        expense_date=expense_date,
        category=payload.category,
        description=payload.description,
        payment_method=payload.payment_method,
        is_restaurant_visit=payload.is_restaurant_visit,
        meal_type=payload.meal_type,
        is_coffee_or_snack=payload.is_coffee_or_snack,
        transport_mode=payload.transport_mode,
        is_shopping=payload.is_shopping,
        is_entertainment=payload.is_entertainment,
        is_impulse=payload.is_impulse,
        activity_tag=payload.activity_tag,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def list_expenses(
    db: Session,
    user: User,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Expense], int]:
    """Return a page of the user's expenses plus the total count."""
    conditions = [Expense.user_id == user.id]
    if date_from is not None:
        conditions.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conditions.append(Expense.expense_date <= date_to)
    if category is not None:
        conditions.append(Expense.category == category.lower())

    total = db.scalar(select(func.count()).select_from(Expense).where(*conditions)) or 0
    rows = db.scalars(
        select(Expense)
        .where(*conditions)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total


def get_expense(db: Session, user: User, expense_id: UUID) -> Expense:
    """Return one expense owned by ``user``.

    A record owned by somebody else is reported as not found, so existence is
    never disclosed across accounts.
    """
    expense = db.scalar(select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id))
    if expense is None:
        raise ExpenseNotFoundError(str(expense_id))
    return expense


_UPDATABLE_FIELDS = (
    "amount",
    "category",
    "description",
    "payment_method",
    "is_restaurant_visit",
    "meal_type",
    "is_coffee_or_snack",
    "transport_mode",
    "is_shopping",
    "is_entertainment",
    "is_impulse",
    "activity_tag",
)


def update_expense(db: Session, user: User, expense_id: UUID, payload: ExpenseUpdate) -> Expense:
    """Apply a partial update to the user's own expense.

    Dates are only touched when the caller supplies them:
    - neither ``spent_at`` nor ``expense_date`` sent -> dates are left untouched;
    - ``spent_at`` only  -> ``expense_date`` is re-derived in the user's timezone;
    - ``expense_date`` only -> timestamp becomes local noon of that date;
    - both -> they must agree, otherwise the update is rejected.
    """
    expense = get_expense(db, user, expense_id)
    changes = payload.model_dump(exclude_unset=True)

    if "spent_at" in changes or "expense_date" in changes:
        spent_at, expense_date = _resolve_dates(
            user,
            changes.get("spent_at"),
            changes.get("expense_date"),
        )
        expense.spent_at = spent_at
        expense.expense_date = expense_date

    for field in _UPDATABLE_FIELDS:
        if field in changes:
            setattr(expense, field, changes[field])

    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(db: Session, user: User, expense_id: UUID) -> None:
    """Delete the user's own expense."""
    expense = get_expense(db, user, expense_id)
    db.delete(expense)
    db.commit()


def total_for_user(db: Session, user: User) -> Decimal:
    """Sum the user's expenses (single currency, so no conversion is needed)."""
    expression = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.user_id == user.id
    )
    return Decimal(db.scalar(expression) or 0)
