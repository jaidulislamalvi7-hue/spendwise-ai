"""Account settings: profile, password, data export and account deletion."""

import streamlit as st

from api_client import ApiError
from app_state import (
    clear_session,
    current_user,
    format_date,
    get_client,
    set_notice,
    set_session,
)
from components.ui import caveat, hero
from config import SUPPORTED_CURRENCIES


def render() -> None:
    """Render the settings page."""
    hero("Settings", "Manage your profile, data and account")

    tab_profile, tab_security, tab_data, tab_danger = st.tabs(
        ["Profile", "Password", "Export data", "Delete account"]
    )
    with tab_profile:
        _render_profile()
    with tab_security:
        _render_password()
    with tab_data:
        _render_export()
    with tab_danger:
        _render_delete()


def _render_profile() -> None:
    user = current_user()
    st.caption(f"Email: {user.get('email', '')}")
    st.caption(f"Member since: {format_date(user.get('created_at'))}")

    with st.form("profile_form"):
        display_name = st.text_input("Display name", value=user.get("display_name") or "")
        col_a, col_b = st.columns(2)
        with col_a:
            currency = st.selectbox(
                "Primary currency",
                SUPPORTED_CURRENCIES,
                index=SUPPORTED_CURRENCIES.index(user.get("primary_currency", "USD"))
                if user.get("primary_currency") in SUPPORTED_CURRENCIES
                else 0,
            )
        with col_b:
            timezone = st.text_input("Timezone (IANA)", value=user.get("timezone", "UTC"))
        submitted = st.form_submit_button("Save profile", type="primary")

    caveat(
        "Changing the currency relabels your totals; amounts are not converted. "
        "Changing the timezone affects how date-only entries are interpreted from "
        "now on. Existing timestamps and expense dates are never rewritten."
    )

    if not submitted:
        return

    payload: dict = {"timezone": timezone.strip() or "UTC", "primary_currency": currency}
    if display_name.strip():
        payload["display_name"] = display_name.strip()

    client = get_client()
    try:
        updated = client.update_profile(payload)
    except ApiError as exc:
        st.error(exc.message)
        return

    # Keep the session profile in sync so currency formatting updates at once.
    token = st.session_state.get("access_token")
    if token:
        set_session(token, updated)
    set_notice("Profile updated.")
    st.rerun()


def _render_password() -> None:
    with st.form("password_form"):
        current = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password", help="At least 8 characters.")
        confirm = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Change password", type="primary")

    if not submitted:
        return
    if not current or not new:
        st.error("Enter your current and new password.")
        return
    if len(new) < 8:
        st.error("New password must be at least 8 characters.")
        return
    if new != confirm:
        st.error("The new passwords do not match.")
        return

    try:
        get_client().change_password(current, new)
    except ApiError as exc:
        st.error(exc.message)
        return
    st.success("Password changed.")


def _render_export() -> None:
    st.write(
        "Download your own data as CSV. Exports include timestamps, local dates, "
        "categories, amounts and lifestyle entries. Only your records are included."
    )
    client = get_client()
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Prepare expenses CSV"):
            try:
                st.session_state["export_expenses"] = client.export_expenses_csv()
            except ApiError as exc:
                st.error(exc.message)
    with col_b:
        if st.button("Prepare lifestyle CSV"):
            try:
                st.session_state["export_lifestyle"] = client.export_lifestyle_csv()
            except ApiError as exc:
                st.error(exc.message)

    expenses_csv = st.session_state.get("export_expenses")
    if expenses_csv:
        st.download_button(
            "Download expenses.csv",
            data=expenses_csv,
            file_name="spendwise-expenses.csv",
            mime="text/csv",
        )
    lifestyle_csv = st.session_state.get("export_lifestyle")
    if lifestyle_csv:
        st.download_button(
            "Download lifestyle.csv",
            data=lifestyle_csv,
            file_name="spendwise-lifestyle.csv",
            mime="text/csv",
        )


def _render_delete() -> None:
    st.error("Deleting your account permanently removes your profile and all data.")
    caveat(
        "Every expense, lifestyle log and budget you own is deleted. This cannot be "
        "undone and there is no recovery."
    )

    with st.form("delete_form"):
        password = st.text_input("Confirm your password", type="password")
        confirmation = st.text_input("Type DELETE to confirm")
        submitted = st.form_submit_button("Permanently delete my account", type="primary")

    if not submitted:
        return
    if confirmation.strip().upper() != "DELETE":
        st.error("Type DELETE to confirm.")
        return
    if not password:
        st.error("Enter your password.")
        return

    try:
        get_client().delete_account(password)
    except ApiError as exc:
        st.error(exc.message)
        return

    clear_session()
    st.session_state.pop("export_expenses", None)
    st.session_state.pop("export_lifestyle", None)
    set_notice("Your account and all associated data were deleted.", "warning")
    st.rerun()
