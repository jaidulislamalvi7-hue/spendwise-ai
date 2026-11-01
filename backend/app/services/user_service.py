"""User account service."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserRegister
from app.security.passwords import hash_password, needs_rehash, verify_password


class EmailAlreadyRegisteredError(Exception):
    """Raised when the email is already in use."""


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return the user with ``email`` (case-insensitive) or None."""
    return db.scalar(select(User).where(User.email == email))


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """Return the user with ``user_id`` or None."""
    return db.get(User, user_id)


def register_user(db: Session, payload: UserRegister) -> User:
    """Create a user with an Argon2 password hash.

    Raises EmailAlreadyRegisteredError when the email exists, relying on the
    database unique constraint rather than a racy pre-check.
    """
    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        primary_currency=payload.primary_currency,
        timezone=payload.timezone,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyRegisteredError(str(payload.email)) from exc
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user when credentials are valid, otherwise None.

    Unknown emails and wrong passwords share one failure mode so the response
    does not disclose which accounts exist.
    """
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
    return user


def create_user_unchecked(
    db: Session,
    *,
    email: str,
    password: str,
    primary_currency: str = "USD",
    timezone: str = "UTC",
) -> User:
    """Create a user without validation (used by test fixtures)."""
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        primary_currency=primary_currency,
        timezone=timezone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_profile(db: Session, user: User, changes: dict) -> User:
    """Apply a partial profile update.

    Only ``display_name``, ``primary_currency`` and ``timezone`` are honoured.
    Changing the timezone affects how *future* date-only entries resolve; stored
    UTC timestamps and existing ``expense_date`` values are never rewritten.
    """
    allowed = {"display_name", "primary_currency", "timezone"}
    for field, value in changes.items():
        if field in allowed:
            setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


class InvalidCredentialsError(Exception):
    """Raised when the supplied current password is wrong."""


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    """Replace the password after verifying the current one."""
    if not verify_password(current_password, user.password_hash):
        raise InvalidCredentialsError("Current password is incorrect")
    if current_password == new_password:
        raise InvalidCredentialsError("New password must differ from the current password")
    user.password_hash = hash_password(new_password)
    db.commit()


def delete_account(db: Session, user: User, password: str) -> None:
    """Permanently delete the user and every record they own.

    Dependent rows are removed by the database ``ON DELETE CASCADE`` rules.
    The password is re-verified so a stolen token alone cannot destroy data.
    """
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Password is incorrect")
    db.delete(user)
    db.commit()
