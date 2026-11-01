"""User and authentication schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants import DEFAULT_CURRENCY, SUPPORTED_CURRENCIES
from app.schemas.common import validate_timezone


class UserRegister(BaseModel):
    """Payload for account registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)
    primary_currency: str = DEFAULT_CURRENCY
    timezone: str = "UTC"

    @field_validator("primary_currency")
    @classmethod
    def _known_currency(cls, value: str) -> str:
        code = value.upper()
        if code not in SUPPORTED_CURRENCIES:
            raise ValueError(f"unsupported currency: {value}")
        return code

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        return validate_timezone(value)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("password must not start or end with whitespace")
        if value.lower() in {"password", "12345678", "password1"}:
            raise ValueError("password is too common")
        return value


class UserLogin(BaseModel):
    """Payload for logging in."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    """Public representation of a user (never includes the password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None
    primary_currency: str
    timezone: str
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    """Partial profile update.

    Only the supplied fields change. Changing ``timezone`` affects how future
    date-only entries are interpreted; stored UTC timestamps and existing
    ``expense_date`` values are never rewritten.
    """

    display_name: str | None = Field(default=None, max_length=120)
    primary_currency: str | None = None
    timezone: str | None = None

    @field_validator("primary_currency")
    @classmethod
    def _known_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = value.upper()
        if code not in SUPPORTED_CURRENCIES:
            raise ValueError(f"unsupported currency: {value}")
        return code

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_timezone(value)


class PasswordChange(BaseModel):
    """Self-service password change."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _not_the_same(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("password must not start or end with whitespace")
        return value


class AccountDeleteRequest(BaseModel):
    """Confirmation payload for account deletion.

    The caller must repeat their password so an intercepted token alone cannot
    destroy the account.
    """

    password: str = Field(min_length=1, max_length=128)
    confirm: str = Field(description="Must be the literal string DELETE")


class TokenResponse(BaseModel):
    """Issued access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
