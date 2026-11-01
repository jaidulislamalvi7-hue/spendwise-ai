"""Authentication pages: register and sign in."""

import streamlit as st

from api_client import ApiClient, ApiError
from app_state import set_notice, set_session
from components.ui import hero
from config import APP_TAGLINE, SUPPORTED_CURRENCIES


def render() -> None:
    """Render the sign-in / registration screen."""
    hero("Welcome to SpendWise AI", APP_TAGLINE)

    login_tab, register_tab = st.tabs(["Sign in", "Create account"])

    with login_tab:
        _render_login()
    with register_tab:
        _render_register()


def _render_login() -> None:
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if not submitted:
        return
    if not email or not password:
        st.error("Enter both your email and password.")
        return

    client = ApiClient()
    try:
        with st.spinner("Signing in\u2026"):
            token = client.login(email.strip(), password)
            authed = ApiClient(token=token["access_token"])
            user = authed.me()
    except ApiError as exc:
        st.error(exc.message)
        return

    set_session(token["access_token"], user)
    set_notice(f"Welcome back, {user.get('email', '')}.")
    st.rerun()


def _render_register() -> None:
    with st.form("register_form"):
        email = st.text_input("Email", key="reg_email", placeholder="you@example.com")
        password = st.text_input(
            "Password", key="reg_password", type="password", help="At least 8 characters."
        )
        display_name = st.text_input("Display name (optional)", key="reg_name")
        col_a, col_b = st.columns(2)
        with col_a:
            currency = st.selectbox(
                "Primary currency",
                SUPPORTED_CURRENCIES,
                index=SUPPORTED_CURRENCIES.index("BDT"),
                help="All amounts are recorded in this currency for now.",
            )
        with col_b:
            timezone = st.text_input("Timezone (IANA)", value="Asia/Dhaka", key="reg_tz")
        submitted = st.form_submit_button(
            "Create account", type="primary", use_container_width=True
        )

    if not submitted:
        return
    if not email or not password:
        st.error("Email and password are required.")
        return
    if len(password) < 8:
        st.error("Password must be at least 8 characters.")
        return

    payload = {
        "email": email.strip(),
        "password": password,
        "primary_currency": currency,
        "timezone": timezone.strip() or "UTC",
    }
    if display_name.strip():
        payload["display_name"] = display_name.strip()

    client = ApiClient()
    try:
        with st.spinner("Creating your account\u2026"):
            client.register(payload)
            token = client.login(payload["email"], password)
            user = ApiClient(token=token["access_token"]).me()
    except ApiError as exc:
        st.error(exc.message)
        return

    set_session(token["access_token"], user)
    set_notice("Account created. Welcome to SpendWise AI!")
    st.rerun()
