"""Pure validation tests: no database required."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.constants import (
    EXPENSE_CATEGORIES,
    MAX_AMOUNT,
    SUPPORTED_CURRENCIES,
)
from app.schemas.common import local_date_from, require_timezone_aware, validate_timezone
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.lifestyle import LifestyleLogCreate, LifestyleLogUpdate
from app.schemas.user import UserRegister

MOMENT = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


class TestTimezoneValidation:
    def test_accepts_known_iana_zone(self) -> None:
        assert validate_timezone("Asia/Dhaka") == "Asia/Dhaka"

    def test_rejects_unknown_zone(self) -> None:
        with pytest.raises(ValueError):
            validate_timezone("Mars/Olympus")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_timezone("  ")

    def test_local_date_uses_user_timezone(self) -> None:
        # 2026-10-30 20:00 UTC is already 2026-10-31 in Dhaka (UTC+6).
        late = datetime(2026, 10, 30, 20, 0, tzinfo=UTC)
        assert local_date_from(late, "UTC").isoformat() == "2026-10-30"
        assert local_date_from(late, "Asia/Dhaka").isoformat() == "2026-10-31"


class TestTimezoneAwareDatetimes:
    def test_naive_datetime_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            require_timezone_aware(datetime(2026, 10, 30, 12, 0))

    def test_aware_datetime_is_accepted(self) -> None:
        assert require_timezone_aware(MOMENT) == MOMENT

    def test_expense_rejects_naive_spent_at(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(amount=Decimal("10.00"), category="food", spent_at=datetime(2026, 10, 30))


class TestExpenseValidation:
    @pytest.mark.parametrize("amount", ["0", "-1.00", "-0.01"])
    def test_amount_must_be_positive(self, amount: str) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(amount=Decimal(amount), category="food", expense_date="2026-10-30")

    def test_amount_rejects_three_decimal_places(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(amount=Decimal("10.005"), category="food", expense_date="2026-10-30")

    def test_amount_rejects_excessive_value(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(
                amount=Decimal(MAX_AMOUNT) + Decimal("1"),
                category="food",
                expense_date="2026-10-30",
            )

    def test_valid_amount_is_preserved(self) -> None:
        expense = ExpenseCreate(amount=Decimal("12.34"), category="food", expense_date="2026-10-30")
        assert expense.amount == Decimal("12.34")

    def test_unknown_category_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(amount=Decimal("5"), category="yachts", expense_date="2026-10-30")

    @pytest.mark.parametrize("category", EXPENSE_CATEGORIES)
    def test_all_central_categories_are_accepted(self, category: str) -> None:
        expense = ExpenseCreate(amount=Decimal("5"), category=category, expense_date="2026-10-30")
        assert expense.category == category

    def test_category_is_normalised(self) -> None:
        expense = ExpenseCreate(amount=Decimal("5"), category="  FOOD ", expense_date="2026-10-30")
        assert expense.category == "food"

    def test_unknown_transport_mode_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(
                amount=Decimal("5"),
                category="transport",
                expense_date="2026-10-30",
                transport_mode="teleport",
            )

    def test_unknown_meal_type_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(
                amount=Decimal("5"),
                category="food",
                expense_date="2026-10-30",
                meal_type="brunch",
            )

    def test_unknown_payment_method_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(
                amount=Decimal("5"),
                category="food",
                expense_date="2026-10-30",
                payment_method="barter",
            )

    def test_requires_spent_at_or_expense_date(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(amount=Decimal("5"), category="food")

    def test_optional_context_may_be_omitted(self) -> None:
        expense = ExpenseCreate(amount=Decimal("5"), category="food", expense_date="2026-10-30")
        assert expense.is_restaurant_visit is None
        assert expense.transport_mode is None
        assert expense.description is None

    def test_update_rejects_zero_amount(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseUpdate(amount=Decimal("0"))

    def test_update_allows_empty_payload(self) -> None:
        assert ExpenseUpdate().model_dump(exclude_unset=True) == {}


class TestLifestyleValidation:
    @pytest.mark.parametrize("stress", [0, 6, -1])
    def test_stress_level_out_of_range(self, stress: int) -> None:
        with pytest.raises(ValidationError):
            LifestyleLogCreate(log_date="2026-10-30", stress_level=stress)

    @pytest.mark.parametrize("stress", [1, 3, 5])
    def test_stress_level_in_range(self, stress: int) -> None:
        log = LifestyleLogCreate(log_date="2026-10-30", stress_level=stress)
        assert log.stress_level == stress

    @pytest.mark.parametrize("hours", ["-0.1", "24.1", "25"])
    def test_sleep_hours_out_of_range(self, hours: str) -> None:
        with pytest.raises(ValidationError):
            LifestyleLogCreate(log_date="2026-10-30", sleep_hours=Decimal(hours))

    def test_sleep_hours_rejects_extra_precision(self) -> None:
        with pytest.raises(ValidationError):
            LifestyleLogCreate(log_date="2026-10-30", sleep_hours=Decimal("7.25"))

    def test_counts_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            LifestyleLogCreate(log_date="2026-10-30", restaurant_visits_count=-1)

    def test_counts_reject_absurd_values(self) -> None:
        with pytest.raises(ValidationError):
            LifestyleLogCreate(log_date="2026-10-30", coffee_snacks_count=999)

    def test_unknown_work_mode_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LifestyleLogCreate(log_date="2026-10-30", work_mode="moon")

    def test_unknown_shopping_activity_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LifestyleLogCreate(log_date="2026-10-30", shopping_activity="extreme")

    def test_all_optional_fields_may_be_missing(self) -> None:
        log = LifestyleLogCreate(log_date="2026-10-30")
        assert log.sleep_hours is None
        assert log.stress_level is None
        assert log.notes is None

    def test_update_does_not_accept_log_date(self) -> None:
        # log_date is immutable, so it is not part of the update schema.
        assert "log_date" not in LifestyleLogUpdate.model_fields


class TestUserValidation:
    def test_unsupported_currency_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserRegister(email="a@example.com", password="supersecret1", primary_currency="XXX")

    def test_supported_currency_is_accepted_and_upper_cased(self) -> None:
        user = UserRegister(email="a@example.com", password="supersecret1", primary_currency="bdt")
        assert user.primary_currency == "BDT"
        assert user.primary_currency in SUPPORTED_CURRENCIES

    def test_invalid_timezone_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserRegister(email="a@example.com", password="supersecret1", timezone="Nowhere/City")

    def test_short_password_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserRegister(email="a@example.com", password="short")

    def test_common_password_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserRegister(email="a@example.com", password="password")

    def test_invalid_email_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserRegister(email="not-an-email", password="supersecret1")
