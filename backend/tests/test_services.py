"""Service-layer tests: user isolation and business rules (requires PostgreSQL)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.lifestyle import LifestyleLogCreate, LifestyleLogUpdate
from app.services import expense_service, lifestyle_service, user_service
from app.services.expense_service import ExpenseNotFoundError
from app.services.lifestyle_service import DuplicateLifestyleLogError, LifestyleLogNotFoundError
from app.services.user_service import EmailAlreadyRegisteredError
from tests.db_guard import requires_db

pytestmark = requires_db


def _user(session, email: str | None = None, currency: str = "USD"):
    return user_service.create_user_unchecked(
        session,
        email=email or f"s-{uuid.uuid4().hex[:10]}@example.com",
        password="supersecret123",
        primary_currency=currency,
    )


def _expense_payload(**overrides) -> ExpenseCreate:
    data = {"amount": Decimal("12.50"), "category": "food", "expense_date": date(2026, 10, 30)}
    data.update(overrides)
    return ExpenseCreate(**data)


class TestUserService:
    def test_register_creates_argon2_hash(self, db_session) -> None:
        from app.schemas.user import UserRegister

        payload = UserRegister(
            email=f"reg-{uuid.uuid4().hex[:8]}@example.com", password="supersecret123"
        )
        user = user_service.register_user(db_session, payload)
        assert user.password_hash.startswith("$argon2")
        assert "supersecret123" not in user.password_hash

    def test_duplicate_registration_raises(self, db_session) -> None:
        from app.schemas.user import UserRegister

        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        payload = UserRegister(email=email, password="supersecret123")
        user_service.register_user(db_session, payload)
        with pytest.raises(EmailAlreadyRegisteredError):
            user_service.register_user(db_session, payload)

    def test_authenticate_with_correct_password(self, db_session) -> None:
        user = _user(db_session)
        assert user_service.authenticate_user(db_session, user.email, "supersecret123") is not None

    def test_authenticate_with_wrong_password(self, db_session) -> None:
        user = _user(db_session)
        assert user_service.authenticate_user(db_session, user.email, "wrong") is None

    def test_authenticate_unknown_email_returns_none(self, db_session) -> None:
        assert user_service.authenticate_user(db_session, "nobody@example.com", "x") is None

    def test_inactive_user_cannot_authenticate(self, db_session) -> None:
        user = _user(db_session)
        user.is_active = False
        db_session.commit()
        assert user_service.authenticate_user(db_session, user.email, "supersecret123") is None


class TestExpenseService:
    def test_create_and_read_back(self, db_session) -> None:
        user = _user(db_session)
        created = expense_service.create_expense(db_session, user, _expense_payload())
        fetched = expense_service.get_expense(db_session, user, created.id)
        assert fetched.amount == Decimal("12.50")

    def test_expense_date_defaults_to_user_timezone(self, db_session) -> None:
        from datetime import UTC, datetime

        user = _user(db_session)
        # 20:00 UTC on 2026-10-30 is 2026-10-31 in Dhaka.
        user.timezone = "Asia/Dhaka"
        db_session.commit()
        created = expense_service.create_expense(
            db_session,
            user,
            ExpenseCreate(
                amount=Decimal("5.00"),
                category="food",
                spent_at=datetime(2026, 10, 30, 20, 0, tzinfo=UTC),
            ),
        )
        assert created.expense_date == date(2026, 10, 31)

    def test_list_filters_by_date_range(self, db_session) -> None:
        user = _user(db_session)
        for day in (1, 5, 10):
            expense_service.create_expense(
                db_session,
                user,
                _expense_payload(expense_date=date(2026, 10, day)),
            )
        rows, total = expense_service.list_expenses(
            db_session, user, date_from=date(2026, 10, 5), date_to=date(2026, 10, 10)
        )
        assert total == 2
        assert {row.expense_date.day for row in rows} == {5, 10}

    def test_list_filters_by_category(self, db_session) -> None:
        user = _user(db_session)
        expense_service.create_expense(db_session, user, _expense_payload(category="food"))
        expense_service.create_expense(db_session, user, _expense_payload(category="transport"))
        rows, total = expense_service.list_expenses(db_session, user, category="transport")
        assert total == 1
        assert rows[0].category == "transport"

    def test_list_does_not_leak_other_users_expenses(self, db_session) -> None:
        alice, bob = _user(db_session), _user(db_session)
        expense_service.create_expense(db_session, alice, _expense_payload())
        rows, total = expense_service.list_expenses(db_session, bob)
        assert total == 0
        assert rows == []

    def test_update_changes_only_given_fields(self, db_session) -> None:
        user = _user(db_session)
        created = expense_service.create_expense(
            db_session, user, _expense_payload(description="lunch")
        )
        updated = expense_service.update_expense(
            db_session, user, created.id, ExpenseUpdate(amount=Decimal("20.00"))
        )
        assert updated.amount == Decimal("20.00")
        assert updated.description == "lunch"
        assert updated.category == "food"

    def test_update_spent_at_only_rederives_date(self, db_session) -> None:
        # PATCH carrying only spent_at must store it in UTC and re-derive the
        # local date in the user's timezone (Dhaka, UTC+6, no DST).
        user = _user(db_session)
        user.timezone = "Asia/Dhaka"
        db_session.commit()
        created = expense_service.create_expense(
            db_session,
            user,
            _expense_payload(expense_date=date(2026, 10, 30)),
        )
        assert created.expense_date == date(2026, 10, 30)

        new_moment = datetime(2026, 10, 30, 9, 0, tzinfo=ZoneInfo("Asia/Dhaka"))
        expense_service.update_expense(
            db_session,
            user,
            created.id,
            ExpenseUpdate(spent_at=new_moment),
        )

        persisted = expense_service.get_expense(db_session, user, created.id)
        # The driver may render a timestamptz in the session's timezone, so
        # assert awareness rather than a specific tzinfo; the exact UTC instant
        # below is what proves correctness.
        assert persisted.spent_at.utcoffset() is not None
        assert persisted.spent_at == datetime(2026, 10, 30, 3, 0, tzinfo=UTC)
        assert persisted.expense_date == date(2026, 10, 30)

    def test_update_spent_at_crossing_local_midnight_changes_date(self, db_session) -> None:
        # 22:00 UTC on 30 Oct is 04:00 on 31 Oct in Dhaka, so the local expense
        # date must roll forward by one day.
        user = _user(db_session)
        user.timezone = "Asia/Dhaka"
        db_session.commit()
        created = expense_service.create_expense(
            db_session,
            user,
            _expense_payload(expense_date=date(2026, 10, 30)),
        )

        new_moment = datetime(2026, 10, 30, 22, 0, tzinfo=UTC)
        expense_service.update_expense(
            db_session,
            user,
            created.id,
            ExpenseUpdate(spent_at=new_moment),
        )

        persisted = expense_service.get_expense(db_session, user, created.id)
        assert persisted.spent_at == new_moment
        assert persisted.expense_date == date(2026, 10, 31)

    def test_delete_removes_expense(self, db_session) -> None:
        user = _user(db_session)
        created = expense_service.create_expense(db_session, user, _expense_payload())
        expense_service.delete_expense(db_session, user, created.id)
        with pytest.raises(ExpenseNotFoundError):
            expense_service.get_expense(db_session, user, created.id)

    def test_get_other_users_expense_raises_not_found(self, db_session) -> None:
        alice, bob = _user(db_session), _user(db_session)
        created = expense_service.create_expense(db_session, alice, _expense_payload())
        with pytest.raises(ExpenseNotFoundError):
            expense_service.get_expense(db_session, bob, created.id)

    def test_update_other_users_expense_raises_not_found(self, db_session) -> None:
        alice, bob = _user(db_session), _user(db_session)
        created = expense_service.create_expense(db_session, alice, _expense_payload())
        with pytest.raises(ExpenseNotFoundError):
            expense_service.update_expense(
                db_session, bob, created.id, ExpenseUpdate(amount=Decimal("1.00"))
            )

    def test_delete_other_users_expense_raises_not_found(self, db_session) -> None:
        alice, bob = _user(db_session), _user(db_session)
        created = expense_service.create_expense(db_session, alice, _expense_payload())
        with pytest.raises(ExpenseNotFoundError):
            expense_service.delete_expense(db_session, bob, created.id)

    def test_other_users_expense_survives_attempted_delete(self, db_session) -> None:
        alice, bob = _user(db_session), _user(db_session)
        created = expense_service.create_expense(db_session, alice, _expense_payload())
        with pytest.raises(ExpenseNotFoundError):
            expense_service.delete_expense(db_session, bob, created.id)
        assert expense_service.get_expense(db_session, alice, created.id).id == created.id

    def test_total_for_user_sums_only_own_expenses(self, db_session) -> None:
        alice, bob = _user(db_session), _user(db_session)
        expense_service.create_expense(db_session, alice, _expense_payload(amount=Decimal("10.25")))
        expense_service.create_expense(db_session, alice, _expense_payload(amount=Decimal("4.75")))
        expense_service.create_expense(db_session, bob, _expense_payload(amount=Decimal("99.00")))
        assert expense_service.total_for_user(db_session, alice) == Decimal("15.00")
        assert expense_service.total_for_user(db_session, bob) == Decimal("99.00")


class TestLifestyleService:
    def test_create_log(self, db_session) -> None:
        user = _user(db_session)
        log = lifestyle_service.create_lifestyle_log(
            db_session,
            user,
            LifestyleLogCreate(
                log_date=date(2026, 10, 30), stress_level=3, sleep_hours=Decimal("7.5")
            ),
        )
        assert log.stress_level == 3

    def test_duplicate_date_raises(self, db_session) -> None:
        user = _user(db_session)
        payload = LifestyleLogCreate(log_date=date(2026, 10, 30))
        lifestyle_service.create_lifestyle_log(db_session, user, payload)
        with pytest.raises(DuplicateLifestyleLogError):
            lifestyle_service.create_lifestyle_log(db_session, user, payload)

    def test_same_date_for_two_users_is_allowed(self, db_session) -> None:
        alice, bob = _user(db_session), _user(db_session)
        payload = LifestyleLogCreate(log_date=date(2026, 10, 30))
        lifestyle_service.create_lifestyle_log(db_session, alice, payload)
        lifestyle_service.create_lifestyle_log(db_session, bob, payload)

    def test_update_log(self, db_session) -> None:
        user = _user(db_session)
        log = lifestyle_service.create_lifestyle_log(
            db_session, user, LifestyleLogCreate(log_date=date(2026, 10, 30), stress_level=2)
        )
        updated = lifestyle_service.update_lifestyle_log(
            db_session, user, log.id, LifestyleLogUpdate(stress_level=5)
        )
        assert updated.stress_level == 5
        assert updated.log_date == date(2026, 10, 30)

    def test_list_scoped_to_user(self, db_session) -> None:
        alice, bob = _user(db_session), _user(db_session)
        lifestyle_service.create_lifestyle_log(
            db_session, alice, LifestyleLogCreate(log_date=date(2026, 10, 30))
        )
        rows, total = lifestyle_service.list_lifestyle_logs(db_session, bob)
        assert total == 0
        assert rows == []

    def test_other_users_log_is_not_found(self, db_session) -> None:
        alice, bob = _user(db_session), _user(db_session)
        log = lifestyle_service.create_lifestyle_log(
            db_session, alice, LifestyleLogCreate(log_date=date(2026, 10, 30))
        )
        with pytest.raises(LifestyleLogNotFoundError):
            lifestyle_service.get_lifestyle_log(db_session, bob, log.id)
        with pytest.raises(LifestyleLogNotFoundError):
            lifestyle_service.update_lifestyle_log(
                db_session, bob, log.id, LifestyleLogUpdate(stress_level=1)
            )
        with pytest.raises(LifestyleLogNotFoundError):
            lifestyle_service.delete_lifestyle_log(db_session, bob, log.id)
