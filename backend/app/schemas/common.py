"""Shared schema helpers."""

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator


def validate_timezone(value: str) -> str:
    """Return a validated IANA timezone identifier."""
    if not value or not value.strip():
        raise ValueError("timezone must not be empty")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown IANA timezone: {value}") from exc
    return value


def require_timezone_aware(value: datetime) -> datetime:
    """Reject naive datetimes."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("datetime must be timezone-aware")
    return value


def local_date_from(moment: datetime, timezone: str) -> date:
    """Return the calendar date of ``moment`` in ``timezone``."""
    return moment.astimezone(ZoneInfo(timezone)).date()


def noon_in_timezone(day: date, timezone: str) -> datetime:
    """Return 12:00 local time on ``day`` in ``timezone``.

    Used when a caller supplies a calendar date without a time: noon keeps the
    resulting UTC timestamp unambiguously inside that local day, so a later
    conversion back to ``timezone`` yields the same date even across DST.
    """
    zone = ZoneInfo(timezone)
    return datetime(day.year, day.month, day.day, 12, 0, tzinfo=zone).astimezone(UTC)


class ExpenseDateError(ValueError):
    """Raised when supplied date and timestamp describe different days."""


def resolve_expense_moment(
    *,
    timezone: str,
    spent_at: datetime | None,
    expense_date: date | None,
    fallback_spent_at: datetime | None = None,
    fallback_expense_date: date | None = None,
) -> tuple[datetime, date]:
    """Resolve a consistent ``(spent_at, expense_date)`` pair.

    Contract:
    - ``expense_date`` alone      -> timestamp is local noon of that date.
    - ``spent_at`` alone          -> date derived in the user's timezone.
    - both                        -> must agree in the user's timezone, else error.
    - neither                     -> the supplied fallbacks are used.

    ``spent_at`` is normalised to UTC; ``expense_date`` is always the calendar
    date in the user's IANA timezone.
    """
    if spent_at is not None and expense_date is not None:
        derived = local_date_from(spent_at, timezone)
        if derived != expense_date:
            raise ExpenseDateError(
                f"expense_date {expense_date} does not match spent_at ({derived} in {timezone})"
            )
        return spent_at.astimezone(UTC), expense_date

    if spent_at is not None:
        return spent_at.astimezone(UTC), local_date_from(spent_at, timezone)

    if expense_date is not None:
        return noon_in_timezone(expense_date, timezone), expense_date

    if fallback_spent_at is not None:
        return fallback_spent_at.astimezone(UTC), local_date_from(fallback_spent_at, timezone)

    if fallback_expense_date is not None:
        return noon_in_timezone(fallback_expense_date, timezone), fallback_expense_date

    raise ExpenseDateError("either spent_at or expense_date must be provided")


class MoneyMixin:
    """Validator helpers for decimal money amounts."""

    @field_validator("amount", "monthly_limit", check_fields=False)
    @classmethod
    def _positive_money(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be greater than zero")
        if value.as_tuple().exponent < -2:  # type: ignore[operator]
            raise ValueError("amount must have at most 2 decimal places")
        return value
