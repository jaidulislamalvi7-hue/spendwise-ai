"""Tests for the frontend API client and formatting helpers.

These run without a Streamlit runtime and without a live backend: HTTP is
mocked through an injected transport.
"""

import httpx
import pytest

from api_client import ApiClient, ApiError, AuthExpiredError, _extract_detail


def _client(handler) -> ApiClient:
    """Build an ApiClient whose HTTP transport is the supplied handler."""
    return ApiClient(
        base_url="http://testserver",
        token="tok",
        transport=httpx.MockTransport(handler),
    )


def _ok(payload, status: int = 200):
    return lambda request: httpx.Response(status, json=payload)


class TestDetailExtraction:
    def test_string_detail(self) -> None:
        response = httpx.Response(400, json={"detail": "Something went wrong"})
        assert _extract_detail(response) == "Something went wrong"

    def test_validation_detail_list(self) -> None:
        response = httpx.Response(
            422, json={"detail": [{"loc": ["body", "amount"], "msg": "must be positive"}]}
        )
        message = _extract_detail(response)
        assert "amount" in message
        assert "must be positive" in message

    def test_plain_text_body(self) -> None:
        response = httpx.Response(500, text="upstream exploded")
        assert "upstream exploded" in _extract_detail(response)


class TestClientRequests:
    def test_authorization_header_and_url(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["auth"] = request.headers.get("Authorization")
            seen["url"] = str(request.url)
            return httpx.Response(200, json={"ok": True})

        assert _client(handler).summary() == {"ok": True}
        assert seen["auth"] == "Bearer tok"
        assert seen["url"] == "http://testserver/api/analytics/summary"

    def test_401_raises_auth_expired(self) -> None:
        client = _client(lambda request: httpx.Response(401, json={"detail": "nope"}))
        with pytest.raises(AuthExpiredError):
            client.summary()

    def test_422_raises_api_error_with_message(self) -> None:
        client = _client(
            lambda request: httpx.Response(
                422, json={"detail": [{"loc": ["body", "amount"], "msg": "invalid"}]}
            )
        )
        with pytest.raises(ApiError) as excinfo:
            client.create_expense({"amount": "0"})
        assert "amount" in str(excinfo.value)

    def test_500_raises_api_error(self) -> None:
        client = _client(lambda request: httpx.Response(500, json={"detail": "boom"}))
        with pytest.raises(ApiError):
            client.summary()

    def test_204_returns_none(self) -> None:
        client = _client(lambda request: httpx.Response(204))
        assert client.delete_expense("abc") is None

    def test_connect_error_is_friendly(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        with pytest.raises(ApiError) as excinfo:
            _client(handler).summary()
        assert "Cannot reach the backend" in excinfo.value.message

    def test_login_posts_credentials(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = request.content.decode()
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})

        client = ApiClient(base_url="http://testserver", transport=httpx.MockTransport(handler))
        assert client.login("a@example.com", "secret123")["access_token"] == "t"
        assert "a@example.com" in seen["body"]


class TestQueryBuilding:
    def _capture(self, **kwargs) -> dict:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["params"] = dict(request.url.params)
            return httpx.Response(200, json={"items": [], "total": 0, "limit": 50, "offset": 0})

        _client(handler).list_expenses(**kwargs)
        return seen["params"]

    def test_filters_are_forwarded(self) -> None:
        params = self._capture(date_from="2026-01-01", category="food", limit=10)
        assert params["date_from"] == "2026-01-01"
        assert params["category"] == "food"
        assert params["limit"] == "10"

    def test_none_filters_are_omitted(self) -> None:
        params = self._capture(category=None, date_from=None, date_to=None)
        assert "category" not in params
        assert "date_from" not in params
        assert "date_to" not in params


class TestFormatting:
    def test_format_currency_uses_currency(self) -> None:
        from formatting import format_currency

        assert format_currency(1234.5, "BDT") == "1,234.50 BDT"

    def test_format_currency_none(self) -> None:
        from formatting import format_currency

        assert format_currency(None, "USD") == "\u2014"

    def test_format_currency_default(self) -> None:
        from formatting import format_currency

        assert format_currency(10.0) == "10.00 USD"

    def test_format_currency_numeric_string(self) -> None:
        # Regression: API Decimal fields serialise as JSON strings.
        from formatting import format_currency

        assert format_currency("25.50", "USD") == "25.50 USD"

    def test_format_currency_decimal(self) -> None:
        from decimal import Decimal

        from formatting import format_currency

        assert format_currency(Decimal("25.50"), "USD") == "25.50 USD"

    def test_format_currency_integer(self) -> None:
        from formatting import format_currency

        assert format_currency(25, "USD") == "25.00 USD"

    def test_format_currency_negative_string(self) -> None:
        from formatting import format_currency

        assert format_currency("-25.50", "USD") == "-25.50 USD"

    def test_format_currency_large_string_is_grouped(self) -> None:
        from formatting import format_currency

        assert format_currency("1234567.891", "USD") == "1,234,567.89 USD"

    def test_format_currency_accepts_valid_grouping(self) -> None:
        from formatting import format_currency

        assert format_currency("1,234.50", "USD") == "1,234.50 USD"
        assert format_currency("12,345,678.90", "USD") == "12,345,678.90 USD"
        assert format_currency("1,234", "USD") == "1,234.00 USD"
        assert format_currency("-1,234.50", "USD") == "-1,234.50 USD"

    def test_format_currency_rejects_malformed_grouping(self) -> None:
        # Stripping commas first would turn these into plausible-looking numbers.
        from formatting import format_currency

        assert format_currency("1,2,3", "USD") == "\u2014"
        assert format_currency("12,34.50", "USD") == "\u2014"
        assert format_currency("1234,567.89", "USD") == "\u2014"
        assert format_currency("1,23", "USD") == "\u2014"

    def test_to_decimal_grouping_rules(self) -> None:
        from decimal import Decimal

        from formatting import to_decimal

        assert to_decimal("1,234.50") == Decimal("1234.50")
        assert to_decimal("12,345,678.90") == Decimal("12345678.90")
        # Plain numeric strings keep working.
        assert to_decimal("1234.50") == Decimal("1234.50")
        assert to_decimal("1,2,3") is None
        assert to_decimal("12,34.50") is None

    def test_format_currency_rejects_non_numeric_string(self) -> None:
        from formatting import format_currency

        assert format_currency("not-a-number", "USD") == "\u2014"

    def test_format_currency_rejects_non_finite(self) -> None:
        from decimal import Decimal

        from formatting import format_currency

        assert format_currency(float("nan"), "USD") == "\u2014"
        assert format_currency(float("inf"), "USD") == "\u2014"
        assert format_currency(Decimal("NaN"), "USD") == "\u2014"

    def test_format_currency_rejects_boolean(self) -> None:
        # bool is an int subclass; True must not render as 1.00.
        from formatting import format_currency

        assert format_currency(True, "USD") == "\u2014"

    def test_format_currency_empty_string(self) -> None:
        from formatting import format_currency

        assert format_currency("", "USD") == "\u2014"

    def test_format_date_iso(self) -> None:
        from formatting import format_date

        assert format_date("2026-01-05") == "05 Jan 2026"

    def test_format_date_iso_datetime_string(self) -> None:
        from formatting import format_date

        assert format_date("2026-01-05T13:45:00+06:00") == "05 Jan 2026"

    def test_format_date_accepts_date_object(self) -> None:
        from datetime import date

        from formatting import format_date

        assert format_date(date(2026, 1, 5)) == "05 Jan 2026"

    def test_format_date_none(self) -> None:
        from formatting import format_date

        assert format_date(None) == "\u2014"

    def test_format_percent(self) -> None:
        from formatting import format_percent

        assert format_percent(12.345) == "12.3%"

    def test_format_percent_numeric_string(self) -> None:
        from formatting import format_percent

        assert format_percent("12.345") == "12.3%"

    def test_format_percent_rejects_non_numeric(self) -> None:
        from formatting import format_percent

        assert format_percent("n/a") == "\u2014"

    def test_format_percent_none(self) -> None:
        from formatting import format_percent

        assert format_percent(None) == "\u2014"

    def test_month_bounds(self) -> None:
        from datetime import date

        from formatting import month_bounds

        start, end = month_bounds(date(2026, 2, 10))
        assert (start, end) == (date(2026, 2, 1), date(2026, 2, 28))

    def test_month_bounds_december(self) -> None:
        from datetime import date

        from formatting import month_bounds

        start, end = month_bounds(date(2026, 12, 15))
        assert (start, end) == (date(2026, 12, 1), date(2026, 12, 31))


class TestParseDate:
    """Regression tests for the date-slicing bug in the expenses edit form."""

    def test_parses_iso_string(self) -> None:
        from datetime import date

        from formatting import parse_date

        assert parse_date("2026-01-05") == date(2026, 1, 5)

    def test_parses_iso_datetime_string(self) -> None:
        from datetime import date

        from formatting import parse_date

        assert parse_date("2026-01-05T13:45:00+06:00") == date(2026, 1, 5)

    def test_date_object_is_returned_unchanged_not_sliced(self) -> None:
        from datetime import date

        from formatting import parse_date

        original = date(2026, 1, 5)
        assert parse_date(original) == original
        assert isinstance(parse_date(original), date)

    def test_datetime_object_is_converted(self) -> None:
        from datetime import date, datetime

        from formatting import parse_date

        assert parse_date(datetime(2026, 1, 5, 13, 45)) == date(2026, 1, 5)

    def test_none_uses_default(self) -> None:
        from datetime import date

        from formatting import parse_date

        assert parse_date(None, default=date(2020, 6, 1)) == date(2020, 6, 1)


class TestConfigContract:
    def test_footer_includes_attribution(self) -> None:
        import config

        assert "Jaidul Islam" in config.FOOTER_TEXT
        assert config.APP_AUTHOR == "Jaidul Islam"

    def test_categories_are_unique(self) -> None:
        import config

        assert "food" in config.EXPENSE_CATEGORIES
        assert len(config.EXPENSE_CATEGORIES) == len(set(config.EXPENSE_CATEGORIES))

    def test_supported_currencies_are_unique_and_uppercase(self) -> None:
        import config

        assert len(config.SUPPORTED_CURRENCIES) == len(set(config.SUPPORTED_CURRENCIES))
        assert all(code.isupper() and len(code) == 3 for code in config.SUPPORTED_CURRENCIES)

    def test_supported_currencies_match_backend_list(self) -> None:
        # Guards against the registration form offering a currency the API rejects.
        import config

        assert "BDT" in config.SUPPORTED_CURRENCIES
        assert "USD" in config.SUPPORTED_CURRENCIES
        assert len(config.SUPPORTED_CURRENCIES) == 18


class TestSessionErrors:
    """The API client must distinguish auth expiry from other failures."""

    def test_401_is_a_distinct_error_type(self) -> None:
        client = _client(lambda request: httpx.Response(401, json={"detail": "nope"}))
        with pytest.raises(AuthExpiredError):
            client.me()

    def test_auth_error_is_catchable_as_api_error(self) -> None:
        # Pages catch ApiError; AuthExpiredError must remain a subclass.
        assert issubclass(AuthExpiredError, ApiError)

    def test_non_auth_failure_is_not_treated_as_expiry(self) -> None:
        client = _client(lambda request: httpx.Response(500, json={"detail": "boom"}))
        with pytest.raises(ApiError) as excinfo:
            client.me()
        assert not isinstance(excinfo.value, AuthExpiredError)

    def test_delete_reports_failure_rather_than_silently_succeeding(self) -> None:
        # A failed delete must raise so the UI can keep the row and show an error.
        client = _client(lambda request: httpx.Response(404, json={"detail": "not found"}))
        with pytest.raises(ApiError):
            client.delete_expense("missing-id")

    def test_delete_success_returns_none(self) -> None:
        client = _client(lambda request: httpx.Response(204))
        assert client.delete_expense("abc") is None
