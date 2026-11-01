"""Lifestyle log schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import (
    MAX_DAILY_COUNT,
    MAX_SLEEP_HOURS,
    SHOPPING_ACTIVITY_SET,
    STRESS_MAX,
    STRESS_MIN,
    TRANSPORT_MODE_SET,
    WORK_MODE_SET,
)


def _check_sleep_precision(value: Decimal | None) -> Decimal | None:
    if value is not None and value.as_tuple().exponent < -1:  # type: ignore[operator]
        raise ValueError("sleep_hours accepts at most one decimal place")
    return value


def _check_work_mode(value: str | None) -> str | None:
    if value is None:
        return None
    mode = value.strip().lower()
    if mode not in WORK_MODE_SET:
        raise ValueError(f"unknown work mode: {value}")
    return mode


def _check_commute_mode(value: str | None) -> str | None:
    if value is None:
        return None
    mode = value.strip().lower()
    if mode not in TRANSPORT_MODE_SET:
        raise ValueError(f"unknown commute mode: {value}")
    return mode


def _check_shopping_activity(value: str | None) -> str | None:
    if value is None:
        return None
    level = value.strip().lower()
    if level not in SHOPPING_ACTIVITY_SET:
        raise ValueError(f"unknown shopping activity: {value}")
    return level


class LifestyleLogCreate(BaseModel):
    """Create payload; a user/date pair may exist only once."""

    log_date: date
    sleep_hours: Decimal | None = Field(default=None, ge=0, le=MAX_SLEEP_HOURS)
    stress_level: int | None = Field(default=None, ge=STRESS_MIN, le=STRESS_MAX)
    work_mode: str | None = None
    commute_mode: str | None = None
    cooked_at_home: bool | None = None
    restaurant_visits_count: int | None = Field(default=None, ge=0, le=MAX_DAILY_COUNT)
    coffee_snacks_count: int | None = Field(default=None, ge=0, le=MAX_DAILY_COUNT)
    shopping_activity: str | None = None
    social_outings_count: int | None = Field(default=None, ge=0, le=MAX_DAILY_COUNT)
    exercise: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("sleep_hours")
    @classmethod
    def _sleep(cls, value: Decimal | None) -> Decimal | None:
        return _check_sleep_precision(value)

    @field_validator("work_mode")
    @classmethod
    def _work(cls, value: str | None) -> str | None:
        return _check_work_mode(value)

    @field_validator("commute_mode")
    @classmethod
    def _commute(cls, value: str | None) -> str | None:
        return _check_commute_mode(value)

    @field_validator("shopping_activity")
    @classmethod
    def _shopping(cls, value: str | None) -> str | None:
        return _check_shopping_activity(value)


class LifestyleLogUpdate(BaseModel):
    """Partial update payload; ``log_date`` is intentionally immutable."""

    sleep_hours: Decimal | None = Field(default=None, ge=0, le=MAX_SLEEP_HOURS)
    stress_level: int | None = Field(default=None, ge=STRESS_MIN, le=STRESS_MAX)
    work_mode: str | None = None
    commute_mode: str | None = None
    cooked_at_home: bool | None = None
    restaurant_visits_count: int | None = Field(default=None, ge=0, le=MAX_DAILY_COUNT)
    coffee_snacks_count: int | None = Field(default=None, ge=0, le=MAX_DAILY_COUNT)
    shopping_activity: str | None = None
    social_outings_count: int | None = Field(default=None, ge=0, le=MAX_DAILY_COUNT)
    exercise: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("sleep_hours")
    @classmethod
    def _sleep(cls, value: Decimal | None) -> Decimal | None:
        return _check_sleep_precision(value)

    @field_validator("work_mode")
    @classmethod
    def _work(cls, value: str | None) -> str | None:
        return _check_work_mode(value)

    @field_validator("commute_mode")
    @classmethod
    def _commute(cls, value: str | None) -> str | None:
        return _check_commute_mode(value)

    @field_validator("shopping_activity")
    @classmethod
    def _shopping(cls, value: str | None) -> str | None:
        return _check_shopping_activity(value)


class LifestyleLogRead(BaseModel):
    """Lifestyle log returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    log_date: date
    sleep_hours: Decimal | None
    stress_level: int | None
    work_mode: str | None
    commute_mode: str | None
    cooked_at_home: bool | None
    restaurant_visits_count: int | None
    coffee_snacks_count: int | None
    shopping_activity: str | None
    social_outings_count: int | None
    exercise: bool | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class LifestyleLogList(BaseModel):
    """Paginated lifestyle log list."""

    items: list[LifestyleLogRead]
    total: int
    limit: int
    offset: int
