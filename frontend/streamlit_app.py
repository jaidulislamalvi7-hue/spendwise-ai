"""SpendWise AI - Streamlit frontend entry point.

Routing is explicit rather than relying on Streamlit's automatic ``pages/``
directory, so unauthenticated visitors can never reach a protected page.

Run from the ``frontend`` directory:
    streamlit run streamlit_app.py
"""

import streamlit as st

from api_client import ApiError, AuthExpiredError
from app_state import (
    clear_session,
    current_user,
    get_client,
    is_authenticated,
    render_notice,
    set_notice,
)
from components.ui import footer, setup_page
from config import APP_NAME
from views import (
    analytics_page,
    auth_page,
    budgets_page,
    dashboard_page,
    expenses_page,
    insights_page,
    lifestyle_page,
    predictions_page,
    settings_page,
    simulator_page,
)

PAGES = {
    "Dashboard": dashboard_page.render,
    "Expenses": expenses_page.render,
    "Budgets": budgets_page.render,
    "Lifestyle": lifestyle_page.render,
    "Analytics": analytics_page.render,
    "Insights": insights_page.render,
    "Predictions": predictions_page.render,
    "What-if simulator": simulator_page.render,
    "Settings": settings_page.render,
}


def _sidebar() -> str:
    """Render the authenticated sidebar and return the selected page."""
    user = current_user()
    with st.sidebar:
        st.markdown(f"### \U0001f4b0 {APP_NAME}")
        st.caption(user.get("email", ""))
        st.caption(f"{user.get('primary_currency', 'USD')} \u00b7 {user.get('timezone', 'UTC')}")
        st.divider()
        choice = st.radio("Navigate", list(PAGES), label_visibility="collapsed")
        st.divider()
        if st.button("Sign out", use_container_width=True):
            clear_session()
            set_notice("You have been signed out.")
            st.rerun()
    return choice


def main() -> None:
    """Application entry point."""
    authenticated = is_authenticated()

    # set_page_config may be called exactly once per rerun, before any other
    # Streamlit output.
    if not authenticated:
        setup_page("Sign in", "\U0001f510")
        auth_page.render()
        footer()
        return

    choice = _sidebar()
    setup_page(choice)
    render_notice()

    # Verify the token once per render. If it is no longer valid, drop the
    # session and return to the sign-in screen instead of leaving a blank page.
    try:
        user = get_client().me()
    except AuthExpiredError:
        clear_session()
        set_notice("Your session has expired. Please sign in again.", "warning")
        st.rerun()
        return
    except ApiError as exc:
        st.warning(f"Could not verify your session: {exc.message}")
        user = None

    if user is not None:
        st.session_state["current_user"] = user

    PAGES[choice]()
    footer()


if __name__ == "__main__":
    main()
