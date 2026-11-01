"""Budget schemas.

A budget is a monthly limit, either overall (``category`` omitted) or for one
category, expressed in the owner's primary currency.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import EXPENSE_CATEGORY_SET


class BudgetUpsert(BaseModel):
    """Create or replace a budget for a category (or the overall budget)."""

    category: str | None = None
    monthly_limit: Decimal = Field(gt=0, le=Decimal("999999999999.99"))

    @field_validator("category")
    @classmethod
    def _known_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        category = value.strip().lower()
        if category not in EXPENSE_CATEGORY_SET:
            raise ValueError(f"unknown category: {value}")
        return category

    @field_validator("monthly_limit")
    @classmethod
    def _two_decimals(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:  # type: ignore[operator]
            raise ValueError("monthly_limit must have at most 2 decimal places")
        return value


class BudgetRead(BaseModel):
    """Stored budget."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str | None
    monthly_limit: Decimal
    created_at: datetime
    updated_at: datetime


class BudgetStatus(BaseModel):
    """Budget with the current month's spending against it."""

    id: UUID
    category: str | None
    monthly_limit: Decimal
    spent: Decimal
    remaining: Decimal
    percentage_used: float
    over_budget: bool
    period_start: str
    period_end: str
