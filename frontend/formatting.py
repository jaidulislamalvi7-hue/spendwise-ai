"""Pure formatting helpers (no Streamlit dependency).

Kept separate from ``app_state`` so formatting logic can be unit-tested without
a Streamlit runtime installed.
"""

import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

DEFAULT_CURRENCY = "USD"

# Thousand separators: every group after the first must be exactly three digits.
_GROUPED_PATTERN = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d*)?$")


def _has_valid_grouping(text: str) -> bool:
    """True when ``text`` uses commas only as correct thousands separators.

    ``"1,234.50"`` and ``"12,345,678.90"`` are valid; ``"1,2,3"`` (groups of the
    wrong size) and ``"12,34.50"`` are not.
    """
    return bool(_GROUPED_PATTERN.match(text))


def to_decimal(value: Any) -> Decimal | None:
    """Convert an API monetary value to ``Decimal``, or None when not numeric.

    The backend serialises ``Decimal`` columns as JSON strings (for example
    ``"25.50"``), so numeric strings must be accepted. Booleans are rejected
    because ``bool`` is a subclass of ``int``. Non-finite values (NaN,
    Infinity) return None rather than being rendered as a misleading amount.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value)) if math.isfinite(value) else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if "," in text:
            # Validate the grouping before removing separators: stripping first
            # would turn "1,2,3" into the apparently valid "123".
            if not _has_valid_grouping(text):
                return None
            text = text.replace(",", "")
        try:
            parsed = Decimal(text)
        except (InvalidOperation, ValueError):
            return None
        return parsed if parsed.is_finite() else None
    return None


def format_currency(
    amount: Any, currency: str | None = None, _fallback: str = DEFAULT_CURRENCY
) -> str:
    """Format an amount in the given (or default) currency.

    Accepts ``Decimal``, ``int``, ``float`` and numeric strings, because API
    responses carry monetary values as strings. Unparseable or non-finite
    values render as an em dash instead of a wrong number.
    """
    value = to_decimal(amount)
    if value is None:
        return "\u2014"
    code = currency or _fallback
    return f"{value:,.2f} {code}"


def format_date(value: str | date | datetime | None) -> str:
    """Format a date for display."""
    if value is None:
        return "\u2014"
    if isinstance(value, datetime):
        return value.date().strftime("%d %b %Y")
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    text = str(value)
    try:
        return date.fromisoformat(text[:10]).strftime("%d %b %Y")
    except ValueError:
        return text


def parse_date(value: str | date | datetime | None, default: date | None = None) -> date:
    """Return a ``date`` from an ISO string or date-like object.

    Strings are truncated to their date part *before* parsing; a ``date`` object
    is returned unchanged and is never sliced.
    """
    if value is None:
        return default or date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def format_percent(value: Any, digits: int = 1) -> str:
    """Format a percentage value, accepting numeric strings from the API."""
    number = to_decimal(value)
    if number is None:
        return "\u2014"
    return f"{number:.{digits}f}%"


def month_bounds(today: date | None = None) -> tuple[date, date]:
    """Return the first and last day of the current month."""
    from datetime import timedelta

    today = today or date.today()
    first = today.replace(day=1)
    if first.month == 12:
        next_month = first.replace(year=first.year + 1, month=1)
    else:
        next_month = first.replace(month=first.month + 1)
    return first, next_month - timedelta(days=1)
