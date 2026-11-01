"""Daily lifestyle log: one row per user per day."""

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import MAX_DAILY_COUNT, MAX_SLEEP_HOURS, STRESS_MAX, STRESS_MIN
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class LifestyleLog(Base):
    """Optional day-level lifestyle factors for one user and one local date."""

    __tablename__ = "lifestyle_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "log_date", name="uq_lifestyle_logs_user_date"),
        CheckConstraint(
            f"stress_level BETWEEN {STRESS_MIN} AND {STRESS_MAX}",
            name="ck_lifestyle_logs_stress_range",
        ),
        CheckConstraint(
            f"sleep_hours >= 0 AND sleep_hours <= {MAX_SLEEP_HOURS}",
            name="ck_lifestyle_logs_sleep_range",
        ),
        CheckConstraint(
            f"restaurant_visits_count BETWEEN 0 AND {MAX_DAILY_COUNT}",
            name="ck_lifestyle_logs_restaurants_range",
        ),
        CheckConstraint(
            f"coffee_snacks_count BETWEEN 0 AND {MAX_DAILY_COUNT}",
            name="ck_lifestyle_logs_coffee_range",
        ),
        CheckConstraint(
            f"social_outings_count BETWEEN 0 AND {MAX_DAILY_COUNT}",
            name="ck_lifestyle_logs_social_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    log_date: Mapped[date] = mapped_column(Date, nullable=False)

    sleep_hours: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    stress_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    commute_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cooked_at_home: Mapped[bool | None] = mapped_column(nullable=True)
    restaurant_visits_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    coffee_snacks_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    shopping_activity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    social_outings_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    exercise: Mapped[bool | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="lifestyle_logs")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LifestyleLog user_id={self.user_id} date={self.log_date}>"
