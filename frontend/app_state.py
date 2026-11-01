"""Streamlit session state, authentication helpers and formatting utilities.

The JWT lives only in ``st.session_state``; it is never written to disk, a URL
or a cookie.
"""

from datetime import date, datetime
from typing import Any

import streamlit as st

import formatting
from api_client import ApiClient, ApiError, AuthExpiredError

SESSION_TOKEN = "access_token"
SESSION_USER = "current_user"
SESSION_NOTICE = "flash_notice"


# -- session ---------------------------------------------------------------


def get_client() -> ApiClient:
    """Return an API client bound to the current session's token."""
    return ApiClient(token=st.session_state.get(SESSION_TOKEN))


def is_authenticated() -> bool:
    """True when a token and user profile are present in the session."""
    return bool(st.session_state.get(SESSION_TOKEN)) and bool(st.session_state.get(SESSION_USER))


def set_session(access_token: str, user: dict[str, Any]) -> None:
    """Store credentials for the current session."""
    st.session_state[SESSION_TOKEN] = access_token
    st.session_state[SESSION_USER] = user


def clear_session() -> None:
    """Drop the session (logout)."""
    for key in (SESSION_TOKEN, SESSION_USER):
        st.session_state.pop(key, None)


def current_user() -> dict[str, Any]:
    """Return the signed-in user profile (empty dict when signed out)."""
    return st.session_state.get(SESSION_USER) or {}


def set_notice(message: str, kind: str = "success") -> None:
    """Queue a one-shot message shown on the next render."""
    st.session_state[SESSION_NOTICE] = {"message": message, "kind": kind}


def render_notice() -> None:
    """Display and clear the queued notice."""
    notice = st.session_state.pop(SESSION_NOTICE, None)
    if not notice:
        return
    renderer = {"success": st.success, "error": st.error, "warning": st.warning}
    renderer.get(notice["kind"], st.info)(notice["message"])


def require_auth() -> None:
    """Stop the page unless the user is signed in."""
    if not is_authenticated():
        st.warning("Please sign in to continue.")
        st.stop()


def handle_api_error(exc: ApiError) -> None:
    """Surface an API error and invalidate the session on auth failure."""
    if isinstance(exc, AuthExpiredError):
        clear_session()
        st.error("Your session has expired. Please sign in again.")
        st.stop()
    st.error(exc.message)


def call_api(function, *args, show_errors: bool = True, **kwargs):
    """Call an API method, handling auth expiry and errors consistently."""
    try:
        return function(*args, **kwargs)
    except AuthExpiredError:
        clear_session()
        st.error("Your session has expired. Please sign in again.")
        st.stop()
    except ApiError as exc:
        if show_errors:
            st.error(exc.message)
        return None


# -- user profile ----------------------------------------------------------


def user_currency() -> str:
    """Return the user's primary currency code (single-currency MVP)."""
    return current_user().get("primary_currency") or "USD"


def user_timezone() -> str:
    """Return the user's IANA timezone, falling back to UTC."""
    return current_user().get("timezone") or "UTC"


def format_currency(amount: float | None, currency: str | None = None) -> str:
    """Format an amount in the user's primary currency."""
    return formatting.format_currency(amount, currency or user_currency())


def format_date(value: str | date | datetime | None) -> str:
    """Format a date for display."""
    return formatting.format_date(value)


def parse_date(value: str | date | datetime | None, default: date | None = None) -> date:
    """Return a ``date``; a date object is returned unchanged, never sliced."""
    return formatting.parse_date(value, default)


def format_percent(value: float | None, digits: int = 1) -> str:
    """Format a percentage value."""
    return formatting.format_percent(value, digits)


def month_bounds(today: date | None = None) -> tuple[date, date]:
    """Return the first and last day of the current month."""
    from datetime import timedelta

    today = today or date.today()
    first = today.replace(day=1)
    if first.month == 12:
        next_month = first.replace(year=first.year + 1, month=1)
    else:
        next_month = first.replace(month=first.month + 1)
    return first, next_month - timedelta(days=1)
