"""Regression tests for the expense date contract.

Covers A1 (contradictory date/timestamp from the client) and B3 (PATCH
silently changing dates). Pure functions only - no database required.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.schemas.common import (
    ExpenseDateError,
    local_date_from,
    noon_in_timezone,
    resolve_expense_moment,
)

DHAKA = "Asia/Dhaka"  # UTC+6, no DST
NEW_YORK = "America/New_York"  # DST-observing


class TestUserSelectedHistoricalDates:
    """A date without a timestamp must not be paired with the current time."""

    def test_date_alone_uses_local_noon(self) -> None:
        spent_at, expense_date = resolve_expense_moment(
            timezone=DHAKA, spent_at=None, expense_date=date(2025, 3, 14)
        )
        assert expense_date == date(2025, 3, 14)
        # Noon in Dhaka is 06:00 UTC.
        assert spent_at == datetime(2025, 3, 14, 6, 0, tzinfo=UTC)

    def test_date_alone_round_trips_to_the_same_day(self) -> None:
        spent_at, expense_date = resolve_expense_moment(
            timezone=NEW_YORK, spent_at=None, expense_date=date(2025, 7, 4)
        )
        # Regardless of DST, converting back must give the requested date.
        assert local_date_from(spent_at, NEW_YORK) == expense_date

    def test_no_timestamp_leaks_the_current_time(self) -> None:
        before = datetime.now(tz=UTC)
        spent_at, _ = resolve_expense_moment(
            timezone=DHAKA, spent_at=None, expense_date=date(2020, 1, 1)
        )
        assert spent_at.year == 2020
        assert spent_at < before


class TestTimestampToLocalDate:
    def test_utc_midnight_maps_to_later_local_day(self) -> None:
        # 20:00 UTC on 30 Oct is 02:00 on 31 Oct in Dhaka.
        moment = datetime(2026, 10, 30, 20, 0, tzinfo=UTC)
        spent_at, expense_date = resolve_expense_moment(
            timezone=DHAKA, spent_at=moment, expense_date=None
        )
        assert expense_date == date(2026, 10, 31)
        assert spent_at == moment

    def test_utc_midnight_maps_to_previous_local_day(self) -> None:
        # 02:00 UTC on 31 Oct is still 30 Oct in New York (UTC-4).
        moment = datetime(2026, 10, 31, 2, 0, tzinfo=UTC)
        _, expense_date = resolve_expense_moment(
            timezone=NEW_YORK, spent_at=moment, expense_date=None
        )
        assert expense_date == date(2026, 10, 30)

    def test_timestamp_is_normalised_to_utc(self) -> None:
        local = datetime(2026, 10, 30, 9, 0, tzinfo=ZoneInfo(DHAKA))
        spent_at, expense_date = resolve_expense_moment(
            timezone=DHAKA, spent_at=local, expense_date=None
        )
        assert spent_at.tzinfo == UTC
        assert spent_at == datetime(2026, 10, 30, 3, 0, tzinfo=UTC)
        assert expense_date == date(2026, 10, 30)


class TestConflictingInput:
    def test_matching_date_and_timestamp_are_accepted(self) -> None:
        moment = datetime(2026, 10, 30, 9, 0, tzinfo=ZoneInfo(DHAKA))
        _, expense_date = resolve_expense_moment(
            timezone=DHAKA, spent_at=moment, expense_date=date(2026, 10, 30)
        )
        assert expense_date == date(2026, 10, 30)

    def test_conflicting_date_and_timestamp_are_rejected(self) -> None:
        moment = datetime(2026, 10, 30, 9, 0, tzinfo=ZoneInfo(DHAKA))
        with pytest.raises(ExpenseDateError) as excinfo:
            resolve_expense_moment(timezone=DHAKA, spent_at=moment, expense_date=date(2026, 1, 1))
        assert "does not match" in str(excinfo.value)

    def test_same_calendar_date_in_utc_but_different_local_day_is_rejected(self) -> None:
        # 20:00 UTC 30 Oct is 31 Oct in Dhaka; claiming the 30th must fail.
        moment = datetime(2026, 10, 30, 20, 0, tzinfo=UTC)
        with pytest.raises(ExpenseDateError):
            resolve_expense_moment(timezone=DHAKA, spent_at=moment, expense_date=date(2026, 10, 30))

    def test_neither_field_is_rejected_without_fallback(self) -> None:
        with pytest.raises(ExpenseDateError):
            resolve_expense_moment(timezone=DHAKA, spent_at=None, expense_date=None)


class TestPatchSemantics:
    """B3: unrelated updates must never move the dates."""

    def test_fallback_preserves_existing_dates(self) -> None:
        stored_moment = datetime(2026, 5, 1, 6, 0, tzinfo=UTC)
        stored_date = date(2026, 5, 1)
        # Simulates PATCH with no date fields: caller passes the stored values.
        spent_at, expense_date = resolve_expense_moment(
            timezone=DHAKA,
            spent_at=None,
            expense_date=None,
            fallback_spent_at=stored_moment,
        )
        assert spent_at == stored_moment
        assert expense_date == stored_date

    def test_date_only_patch_sets_noon_of_that_day(self) -> None:
        spent_at, expense_date = resolve_expense_moment(
            timezone=DHAKA, spent_at=None, expense_date=date(2026, 2, 2)
        )
        assert expense_date == date(2026, 2, 2)
        assert spent_at.hour == 6  # 12:00 Dhaka in UTC

    def test_timestamp_only_patch_rederives_the_date(self) -> None:
        moment = datetime(2026, 2, 2, 22, 0, tzinfo=UTC)  # 03 Feb 04:00 Dhaka
        _, expense_date = resolve_expense_moment(timezone=DHAKA, spent_at=moment, expense_date=None)
        assert expense_date == date(2026, 2, 3)

    def test_conflicting_patch_is_rejected(self) -> None:
        moment = datetime(2026, 2, 2, 22, 0, tzinfo=UTC)
        with pytest.raises(ExpenseDateError):
            resolve_expense_moment(timezone=DHAKA, spent_at=moment, expense_date=date(2026, 2, 2))


class TestTimezoneBoundaries:
    def test_noon_helper_stays_inside_the_local_day_across_dst(self) -> None:
        # US DST begins 2025-03-09; noon must still be that local date.
        for day in (date(2025, 3, 8), date(2025, 3, 9), date(2025, 3, 10)):
            moment = noon_in_timezone(day, NEW_YORK)
            assert local_date_from(moment, NEW_YORK) == day

    def test_noon_helper_handles_dst_end(self) -> None:
        for day in (date(2025, 11, 1), date(2025, 11, 2), date(2025, 11, 3)):
            moment = noon_in_timezone(day, NEW_YORK)
            assert local_date_from(moment, NEW_YORK) == day

    def test_utc_timezone_is_identity_for_dates(self) -> None:
        moment = datetime(2026, 10, 30, 23, 30, tzinfo=UTC)
        _, expense_date = resolve_expense_moment(timezone="UTC", spent_at=moment, expense_date=None)
        assert expense_date == date(2026, 10, 30)

    def test_day_boundary_just_before_midnight_local(self) -> None:
        # 23:30 local on 30 Oct in Dhaka == 17:30 UTC on 30 Oct.
        moment = datetime(2026, 10, 30, 23, 30, tzinfo=ZoneInfo(DHAKA))
        _, expense_date = resolve_expense_moment(timezone=DHAKA, spent_at=moment, expense_date=None)
        assert expense_date == date(2026, 10, 30)

    def test_day_boundary_just_after_midnight_local(self) -> None:
        moment = datetime(2026, 10, 31, 0, 30, tzinfo=ZoneInfo(DHAKA))
        _, expense_date = resolve_expense_moment(timezone=DHAKA, spent_at=moment, expense_date=None)
        assert expense_date == date(2026, 10, 31)
