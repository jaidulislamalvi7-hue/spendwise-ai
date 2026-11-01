"""Lifestyle log service, scoped to the owning user."""

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lifestyle_log import LifestyleLog
from app.models.user import User
from app.schemas.lifestyle import LifestyleLogCreate, LifestyleLogUpdate


class LifestyleLogNotFoundError(Exception):
    """Raised when a lifestyle log does not exist for this user."""


class DuplicateLifestyleLogError(Exception):
    """Raised when the user already has a log for that date."""


def create_lifestyle_log(db: Session, user: User, payload: LifestyleLogCreate) -> LifestyleLog:
    """Create a daily log; a user/date pair may exist only once."""
    log = LifestyleLog(user_id=user.id, **payload.model_dump())
    db.add(log)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateLifestyleLogError(str(payload.log_date)) from exc
    db.refresh(log)
    return log


def list_lifestyle_logs(
    db: Session,
    user: User,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[LifestyleLog], int]:
    """Return a page of the user's lifestyle logs plus the total count."""
    conditions = [LifestyleLog.user_id == user.id]
    if date_from is not None:
        conditions.append(LifestyleLog.log_date >= date_from)
    if date_to is not None:
        conditions.append(LifestyleLog.log_date <= date_to)

    total = db.scalar(select(func.count()).select_from(LifestyleLog).where(*conditions)) or 0
    rows = db.scalars(
        select(LifestyleLog)
        .where(*conditions)
        .order_by(LifestyleLog.log_date.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total


def get_lifestyle_log(db: Session, user: User, log_id: UUID) -> LifestyleLog:
    """Return one of the user's logs; other users' logs are reported missing."""
    log = db.scalar(
        select(LifestyleLog).where(LifestyleLog.id == log_id, LifestyleLog.user_id == user.id)
    )
    if log is None:
        raise LifestyleLogNotFoundError(str(log_id))
    return log


def get_lifestyle_log_by_date(db: Session, user: User, log_date: date) -> LifestyleLog | None:
    """Return the user's log for a specific date, if any."""
    return db.scalar(
        select(LifestyleLog).where(
            LifestyleLog.user_id == user.id, LifestyleLog.log_date == log_date
        )
    )


def update_lifestyle_log(
    db: Session, user: User, log_id: UUID, payload: LifestyleLogUpdate
) -> LifestyleLog:
    """Apply a partial update; log_date is immutable."""
    log = get_lifestyle_log(db, user, log_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return log


def delete_lifestyle_log(db: Session, user: User, log_id: UUID) -> None:
    """Delete one of the user's logs."""
    log = get_lifestyle_log(db, user, log_id)
    db.delete(log)
    db.commit()
