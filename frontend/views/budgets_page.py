"""Budgets: set monthly limits and track spending against them."""

from typing import Any

import streamlit as st

from api_client import ApiError
from app_state import call_api, format_currency, format_percent, get_client, set_notice
from components.ui import confirm_delete, empty_state, hero
from config import EXPENSE_CATEGORIES

OVERALL_LABEL = "Overall (all categories)"


def _label(category: str | None) -> str:
    if category is None:
        return OVERALL_LABEL
    return category.replace("_", " ").title()


def render() -> None:
    """Render the budgets page."""
    hero("Budgets", "Monthly limits and how much of each one you have used")

    client = get_client()
    with st.spinner("Loading your budgets\u2026"):
        statuses = call_api(client.budgets)

    with st.form("budget_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            choice = st.selectbox("Category", [OVERALL_LABEL, *EXPENSE_CATEGORIES])
        with col_b:
            limit = st.number_input("Monthly limit", min_value=0.01, step=10.0, format="%.2f")
        submitted = st.form_submit_button("Save budget", type="primary")

    if submitted:
        category = None if choice == OVERALL_LABEL else choice
        result = call_api(client.upsert_budget, category, float(limit))
        if result is not None:
            set_notice(f"Budget saved for {_label(category)}.")
            st.rerun()

    if statuses is None:
        return

    if not statuses:
        empty_state(
            "No budgets yet",
            "Set a monthly limit above to start tracking your spending against it.",
            "\U0001f4b0",
        )
        return

    st.divider()
    for status in statuses:
        _render_budget(status, client)


def _render_budget(status: dict[str, Any], client) -> None:
    used = float(status["percentage_used"])
    spent = float(status["spent"])
    limit = float(status["monthly_limit"])
    remaining = float(status["remaining"])

    with st.container():
        header, action = st.columns([5, 2])
        with header:
            st.markdown(f"**{_label(status['category'])}**")
            st.caption(f"Period {status['period_start']} to {status['period_end']}")
        with action:
            if confirm_delete(f"budget_{status['id']}", "Remove budget"):
                try:
                    client.delete_budget(status["id"])
                except ApiError as exc:
                    st.error(exc.message)
                    st.session_state.pop(f"confirm_budget_{status['id']}", None)
                else:
                    st.session_state.pop(f"confirm_budget_{status['id']}", None)
                    set_notice("Budget removed.")
                    st.rerun()

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Limit", format_currency(limit))
        col_b.metric("Spent", format_currency(spent))
        col_c.metric("Remaining", format_currency(remaining))

        # Progress is clamped for the bar but the caption keeps the real value.
        st.progress(min(max(used / 100.0, 0.0), 1.0))
        if status["over_budget"]:
            over = abs(remaining)
            st.error(
                f"Over budget by {format_currency(over)} "
                f"({format_percent(used)} of the limit used)."
            )
        else:
            st.caption(f"{format_percent(used)} of the limit used this month.")
        st.divider()
