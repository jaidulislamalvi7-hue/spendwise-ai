"""Initial schema: users, expenses, lifestyle_logs, budgets.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("primary_currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("char_length(primary_currency) = 3", name="ck_users_currency_length"),
        sa.CheckConstraint("char_length(timezone) > 0", name="ck_users_timezone_not_empty"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "expenses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("spent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.String(length=30), nullable=True),
        sa.Column("is_restaurant_visit", sa.Boolean(), nullable=True),
        sa.Column("meal_type", sa.String(length=20), nullable=True),
        sa.Column("is_coffee_or_snack", sa.Boolean(), nullable=True),
        sa.Column("transport_mode", sa.String(length=20), nullable=True),
        sa.Column("is_shopping", sa.Boolean(), nullable=True),
        sa.Column("is_entertainment", sa.Boolean(), nullable=True),
        sa.Column("is_impulse", sa.Boolean(), nullable=True),
        sa.Column("activity_tag", sa.String(length=60), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.CheckConstraint("char_length(category) > 0", name="ck_expenses_category_not_empty"),
    )
    op.create_index("ix_expenses_user_id", "expenses", ["user_id"])
    op.create_index("ix_expenses_user_date", "expenses", ["user_id", "expense_date"])
    op.create_index("ix_expenses_user_category", "expenses", ["user_id", "category"])
    op.create_index("ix_expenses_user_transport_mode", "expenses", ["user_id", "transport_mode"])

    op.create_table(
        "lifestyle_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("sleep_hours", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("stress_level", sa.SmallInteger(), nullable=True),
        sa.Column("work_mode", sa.String(length=20), nullable=True),
        sa.Column("commute_mode", sa.String(length=20), nullable=True),
        sa.Column("cooked_at_home", sa.Boolean(), nullable=True),
        sa.Column("restaurant_visits_count", sa.SmallInteger(), nullable=True),
        sa.Column("coffee_snacks_count", sa.SmallInteger(), nullable=True),
        sa.Column("shopping_activity", sa.String(length=20), nullable=True),
        sa.Column("social_outings_count", sa.SmallInteger(), nullable=True),
        sa.Column("exercise", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "log_date", name="uq_lifestyle_logs_user_date"),
        sa.CheckConstraint("stress_level BETWEEN 1 AND 5", name="ck_lifestyle_logs_stress_range"),
        sa.CheckConstraint(
            "sleep_hours >= 0 AND sleep_hours <= 24", name="ck_lifestyle_logs_sleep_range"
        ),
        sa.CheckConstraint(
            "restaurant_visits_count BETWEEN 0 AND 50",
            name="ck_lifestyle_logs_restaurants_range",
        ),
        sa.CheckConstraint(
            "coffee_snacks_count BETWEEN 0 AND 50", name="ck_lifestyle_logs_coffee_range"
        ),
        sa.CheckConstraint(
            "social_outings_count BETWEEN 0 AND 50", name="ck_lifestyle_logs_social_range"
        ),
    )
    op.create_index("ix_lifestyle_logs_user_id", "lifestyle_logs", ["user_id"])

    op.create_table(
        "budgets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("monthly_limit", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "category", name="uq_budgets_user_category"),
        sa.CheckConstraint("monthly_limit > 0", name="ck_budgets_limit_positive"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_budgets_user_id", table_name="budgets")
    op.drop_table("budgets")
    op.drop_index("ix_lifestyle_logs_user_id", table_name="lifestyle_logs")
    op.drop_table("lifestyle_logs")
    op.drop_index("ix_expenses_user_transport_mode", table_name="expenses")
    op.drop_index("ix_expenses_user_category", table_name="expenses")
    op.drop_index("ix_expenses_user_date", table_name="expenses")
    op.drop_index("ix_expenses_user_id", table_name="expenses")
    op.drop_table("expenses")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
