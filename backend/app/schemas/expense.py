"""Expense schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.constants import (
    EXPENSE_CATEGORY_SET,
    MAX_AMOUNT,
    MEAL_TYPE_SET,
    MIN_AMOUNT,
    PAYMENT_METHOD_SET,
    TRANSPORT_MODE_SET,
)
from app.schemas.common import MoneyMixin, require_timezone_aware


def _category(value: str) -> str:
    category = value.strip().lower()
    if category not in EXPENSE_CATEGORY_SET:
        raise ValueError(f"unknown category: {value}")
    return category


def _optional_category(value: str | None) -> str | None:
    return None if value is None else _category(value)


def _payment_method(value: str | None) -> str | None:
    if value is None:
        return None
    method = value.strip().lower()
    if method not in PAYMENT_METHOD_SET:
        raise ValueError(f"unknown payment method: {value}")
    return method


def _meal_type(value: str | None) -> str | None:
    if value is None:
        return None
    meal = value.strip().lower()
    if meal not in MEAL_TYPE_SET:
        raise ValueError(f"unknown meal type: {value}")
    return meal


def _transport_mode(value: str | None) -> str | None:
    if value is None:
        return None
    mode = value.strip().lower()
    if mode not in TRANSPORT_MODE_SET:
        raise ValueError(f"unknown transport mode: {value}")
    return mode


def _aware_or_none(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return require_timezone_aware(value)


class ExpenseCreate(MoneyMixin, BaseModel):
    """Create payload. ``user_id`` is never accepted from the client."""

    amount: Decimal = Field(ge=Decimal(MIN_AMOUNT), le=Decimal(MAX_AMOUNT))
    spent_at: datetime | None = None
    expense_date: date | None = None
    category: str
    description: str | None = Field(default=None, max_length=500)
    payment_method: str | None = None

    is_restaurant_visit: bool | None = None
    meal_type: str | None = None
    is_coffee_or_snack: bool | None = None
    transport_mode: str | None = None
    is_shopping: bool | None = None
    is_entertainment: bool | None = None
    is_impulse: bool | None = None
    activity_tag: str | None = Field(default=None, max_length=60)

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str) -> str:
        return _category(value)

    @field_validator("payment_method")
    @classmethod
    def _check_payment_method(cls, value: str | None) -> str | None:
        return _payment_method(value)

    @field_validator("meal_type")
    @classmethod
    def _check_meal_type(cls, value: str | None) -> str | None:
        return _meal_type(value)

    @field_validator("transport_mode")
    @classmethod
    def _check_transport_mode(cls, value: str | None) -> str | None:
        return _transport_mode(value)

    @field_validator("spent_at")
    @classmethod
    def _check_spent_at(cls, value: datetime | None) -> datetime | None:
        return _aware_or_none(value)

    @model_validator(mode="after")
    def _require_moment(self) -> "ExpenseCreate":
        if self.spent_at is None and self.expense_date is None:
            raise ValueError("either spent_at or expense_date must be provided")
        return self


# Columns that are NOT NULL in the database. An explicit null for any of these
# in a PATCH payload is a validation error, not a database error.
_NON_NULLABLE_FIELDS = ("amount", "spent_at", "expense_date", "category")


class ExpenseUpdate(BaseModel):
    """Partial update payload; only provided fields are changed."""

    amount: Decimal | None = Field(default=None, ge=Decimal(MIN_AMOUNT), le=Decimal(MAX_AMOUNT))
    spent_at: datetime | None = None
    expense_date: date | None = None
    category: str | None = None
    description: str | None = Field(default=None, max_length=500)
    payment_method: str | None = None

    is_restaurant_visit: bool | None = None
    meal_type: str | None = None
    is_coffee_or_snack: bool | None = None
    transport_mode: str | None = None
    is_shopping: bool | None = None
    is_entertainment: bool | None = None
    is_impulse: bool | None = None
    activity_tag: str | None = Field(default=None, max_length=60)

    @field_validator("amount")
    @classmethod
    def _check_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value.as_tuple().exponent < -2:  # type: ignore[operator]
            raise ValueError("amount must have at most 2 decimal places")
        return value

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str | None) -> str | None:
        return _optional_category(value)

    @field_validator("payment_method")
    @classmethod
    def _check_payment_method(cls, value: str | None) -> str | None:
        return _payment_method(value)

    @field_validator("meal_type")
    @classmethod
    def _check_meal_type(cls, value: str | None) -> str | None:
        return _meal_type(value)

    @field_validator("transport_mode")
    @classmethod
    def _check_transport_mode(cls, value: str | None) -> str | None:
        return _transport_mode(value)

    @field_validator("spent_at")
    @classmethod
    def _check_spent_at(cls, value: datetime | None) -> datetime | None:
        return _aware_or_none(value)

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> "ExpenseUpdate":
        # Omitted fields stay untouched; explicitly sending null for a required
        # column fails here (HTTP 422) instead of hitting a NOT NULL constraint.
        for field in _NON_NULLABLE_FIELDS:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ExpenseRead(BaseModel):
    """Expense returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    spent_at: datetime
    expense_date: date
    category: str
    description: str | None
    payment_method: str | None
    is_restaurant_visit: bool | None
    meal_type: str | None
    is_coffee_or_snack: bool | None
    transport_mode: str | None
    is_shopping: bool | None
    is_entertainment: bool | None
    is_impulse: bool | None
    activity_tag: str | None
    created_at: datetime
    updated_at: datetime


class ExpenseList(BaseModel):
    """Paginated expense list."""

    items: list[ExpenseRead]
    total: int
    limit: int
    offset: int
