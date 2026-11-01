"""Model constraint and relationship tests (requires PostgreSQL)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Budget, Expense, LifestyleLog, User
from tests.db_guard import requires_db

pytestmark = requires_db


def _user(session, email: str | None = None) -> User:
    from app.services.user_service import create_user_unchecked

    return create_user_unchecked(
        session, email=email or f"m-{uuid.uuid4().hex[:10]}@example.com", password="supersecret123"
    )


class TestUserModel:
    def test_email_is_stored(self, db_session) -> None:
        user = _user(db_session, "CaseCase@Example.com")
        assert user.email == "casecase@example.com"

    def test_email_uniqueness_is_case_insensitive(self, db_session) -> None:
        _user(db_session, "dupe@example.com")
        with pytest.raises(IntegrityError):
            _user(db_session, "DUPE@example.com")

    def test_default_currency_and_timezone(self, db_session) -> None:
        user = _user(db_session)
        assert user.primary_currency == "USD"
        assert user.timezone == "UTC"

    def test_password_hash_is_never_plaintext(self, db_session) -> None:
        user = _user(db_session)
        assert "supersecret123" not in user.password_hash
        assert user.password_hash.startswith("$argon2")


class TestExpenseModel:
    def test_relationship_from_user_to_expenses(self, db_session) -> None:
        user = _user(db_session)
        db_session.add(
            Expense(
                user_id=user.id,
                amount=Decimal("10.00"),
                spent_at=datetime.now(UTC),
                expense_date=date(2026, 10, 30),
                category="food",
            )
        )
        db_session.commit()
        db_session.refresh(user)
        assert len(user.expenses) == 1

    def test_negative_amount_violates_check_constraint(self, db_session) -> None:
        user = _user(db_session)
        db_session.add(
            Expense(
                user_id=user.id,
                amount=Decimal("-1.00"),
                spent_at=datetime.now(UTC),
                expense_date=date(2026, 10, 30),
                category="food",
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_amount_round_trips_with_two_decimals(self, db_session) -> None:
        user = _user(db_session)
        expense = Expense(
            user_id=user.id,
            amount=Decimal("19.99"),
            spent_at=datetime.now(UTC),
            expense_date=date(2026, 10, 30),
            category="food",
        )
        db_session.add(expense)
        db_session.commit()
        db_session.refresh(expense)
        assert expense.amount == Decimal("19.99")

    def test_deleting_user_cascades_to_expenses(self, db_session) -> None:
        user = _user(db_session)
        expense = Expense(
            user_id=user.id,
            amount=Decimal("5.00"),
            spent_at=datetime.now(UTC),
            expense_date=date(2026, 10, 30),
            category="food",
        )
        db_session.add(expense)
        db_session.commit()
        expense_id = expense.id

        db_session.delete(user)
        db_session.commit()
        # The cascade happens in the database, so the session's identity map
        # still holds the (now deleted) row. Expire it to read real DB state.
        db_session.expire_all()

        assert db_session.get(Expense, expense_id) is None


class TestLifestyleLogModel:
    def test_one_log_per_user_per_date(self, db_session) -> None:
        user = _user(db_session)
        day = date(2026, 10, 30)
        db_session.add(LifestyleLog(user_id=user.id, log_date=day))
        db_session.commit()

        db_session.add(LifestyleLog(user_id=user.id, log_date=day))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_stress_level_check_constraint(self, db_session) -> None:
        user = _user(db_session)
        db_session.add(LifestyleLog(user_id=user.id, log_date=date(2026, 10, 30), stress_level=9))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_deleting_user_cascades_to_lifestyle_logs(self, db_session) -> None:
        user = _user(db_session)
        log = LifestyleLog(user_id=user.id, log_date=date(2026, 10, 30))
        db_session.add(log)
        db_session.commit()
        log_id = log.id

        db_session.delete(user)
        db_session.commit()
        # The cascade happens in the database, so the session's identity map
        # still holds the (now deleted) row. Expire it to read real DB state.
        db_session.expire_all()

        assert db_session.get(LifestyleLog, log_id) is None


class TestBudgetModel:
    def test_budget_belongs_to_user(self, db_session) -> None:
        user = _user(db_session)
        budget = Budget(user_id=user.id, category="food", monthly_limit=Decimal("200.00"))
        db_session.add(budget)
        db_session.commit()
        db_session.refresh(user)
        assert [b.category for b in user.budgets] == ["food"]

    def test_negative_budget_is_rejected(self, db_session) -> None:
        user = _user(db_session)
        db_session.add(Budget(user_id=user.id, monthly_limit=Decimal("-5.00")))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_deleting_user_cascades_to_budgets(self, db_session) -> None:
        user = _user(db_session)
        budget = Budget(user_id=user.id, monthly_limit=Decimal("100.00"))
        db_session.add(budget)
        db_session.commit()
        budget_id = budget.id

        db_session.delete(user)
        db_session.commit()
        # The cascade happens in the database, so the session's identity map
        # still holds the (now deleted) row. Expire it to read real DB state.
        db_session.expire_all()

        assert db_session.get(Budget, budget_id) is None
