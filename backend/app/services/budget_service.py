"""Budget service: monthly limits and spending-against-budget status.

All queries are scoped to the owning user.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.expense import Expense
from app.models.user import User
from app.schemas.budget import BudgetStatus, BudgetUpsert


class BudgetNotFoundError(Exception):
    """Raised when a budget does not exist for this user."""


def month_bounds(today: date | None = None) -> tuple[date, date]:
    """Return the first and last day of the month containing ``today``."""
    today = today or date.today()
    first = today.replace(day=1)
    if first.month == 12:
        next_month = first.replace(year=first.year + 1, month=1)
    else:
        next_month = first.replace(month=first.month + 1)
    from datetime import timedelta

    return first, next_month - timedelta(days=1)


def _month_bounds_for_user(user: User) -> tuple[date, date]:
    """Month bounds in the user's timezone, not the server's."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    local_today = datetime.now(tz=ZoneInfo(user.timezone)).date()
    return month_bounds(local_today)


def list_budgets(db: Session, user: User) -> list[Budget]:
    """Return all of the user's budgets."""
    return list(
        db.scalars(select(Budget).where(Budget.user_id == user.id).order_by(Budget.category)).all()
    )


def get_budget(db: Session, user: User, budget_id: UUID) -> Budget:
    """Return one of the user's budgets; others are reported missing."""
    budget = db.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id))
    if budget is None:
        raise BudgetNotFoundError(str(budget_id))
    return budget


def get_budget_by_category(db: Session, user: User, category: str | None) -> Budget | None:
    """Return the user's budget for ``category`` (None = overall), if any.

    A NULL category means the overall budget, so it needs ``IS NULL``; a real
    category must use an equality comparison. ``is_(value)`` with a string
    renders ``IS %s``, which PostgreSQL rejects.
    """
    condition = Budget.category.is_(None) if category is None else Budget.category == category
    return db.scalar(select(Budget).where(Budget.user_id == user.id, condition))


def upsert_budget(db: Session, user: User, payload: BudgetUpsert) -> Budget:
    """Create or update the budget for a category.

    The database enforces one budget per (user, category); this method updates
    the existing row instead of inserting a duplicate.
    """
    existing = get_budget_by_category(db, user, payload.category)
    if existing is None:
        budget = Budget(
            user_id=user.id,
            category=payload.category,
            monthly_limit=payload.monthly_limit,
        )
        db.add(budget)
    else:
        budget = existing
        budget.monthly_limit = payload.monthly_limit
    db.commit()
    db.refresh(budget)
    return budget


def delete_budget(db: Session, user: User, budget_id: UUID) -> None:
    """Delete one of the user's budgets."""
    budget = get_budget(db, user, budget_id)
    db.delete(budget)
    db.commit()


def spending_in_period(
    db: Session, user: User, start: date, end: date, category: str | None
) -> Decimal:
    """Sum the user's spending in a date range, optionally for one category."""
    conditions = [
        Expense.user_id == user.id,
        Expense.expense_date >= start,
        Expense.expense_date <= end,
    ]
    if category is not None:
        conditions.append(Expense.category == category)
    total = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(*conditions))
    return Decimal(total or 0)


def status_for(db: Session, user: User, budget: Budget) -> BudgetStatus:
    """Return the budget with this month's spending applied."""
    start, end = _month_bounds_for_user(user)
    spent = spending_in_period(db, user, start, end, budget.category)
    limit = Decimal(budget.monthly_limit)
    remaining = limit - spent
    percentage = float(spent / limit * 100) if limit else 0.0
    return BudgetStatus(
        id=budget.id,
        category=budget.category,
        monthly_limit=limit,
        spent=spent,
        remaining=remaining,
        percentage_used=round(percentage, 2),
        over_budget=spent > limit,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
    )


def status_list(db: Session, user: User) -> list[BudgetStatus]:
    """Return status for every budget the user has."""
    return [status_for(db, user, budget) for budget in list_budgets(db, user)]
