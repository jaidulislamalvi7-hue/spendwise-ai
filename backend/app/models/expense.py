"""Expense model, including optional transaction-level lifestyle context."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Expense(Base):
    """A single expense belonging to exactly one user.

    Amounts are always in the owning user's primary currency; the application
    performs no cross-currency arithmetic.
    """

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint("char_length(category) > 0", name="ck_expenses_category_not_empty"),
        Index("ix_expenses_user_date", "user_id", "expense_date"),
        Index("ix_expenses_user_category", "user_id", "category"),
        Index("ix_expenses_user_transport_mode", "user_id", "transport_mode"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Exact moment of the spend, stored timezone-aware (UTC).
    spent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # User-local calendar date used for grouping and analytics.
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Transaction-level context (all optional).
    is_restaurant_visit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    meal_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_coffee_or_snack: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    transport_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_shopping: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_entertainment: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_impulse: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    activity_tag: Mapped[str | None] = mapped_column(String(60), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="expenses")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Expense id={self.id} amount={self.amount} category={self.category!r}>"
