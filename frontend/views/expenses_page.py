"""Expense management: add, filter, edit and delete."""

from datetime import date

import streamlit as st

from api_client import ApiError
from app_state import call_api, format_currency, format_date, get_client, parse_date, set_notice
from components.ui import confirm_delete, empty_state, hero
from config import EXPENSE_CATEGORIES, MEAL_TYPES, PAYMENT_METHODS, TRANSPORT_MODES


def render() -> None:
    """Render the expenses page."""
    hero("Expenses", "Record and manage your daily spending")

    tab_add, tab_history = st.tabs(["Add expense", "History"])
    with tab_add:
        _render_add_form()
    with tab_history:
        _render_history()


def _render_add_form() -> None:
    with st.form("add_expense", clear_on_submit=True):
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            amount = st.number_input("Amount", min_value=0.01, step=1.0, format="%.2f")
        with col_b:
            category = st.selectbox(
                "Category", EXPENSE_CATEGORIES, format_func=lambda c: c.replace("_", " ").title()
            )
        with col_c:
            spent_on = st.date_input("Date", value=date.today(), max_value=date.today())

        description = st.text_input("Description (optional)", max_chars=500)
        payment_method = st.selectbox(
            "Payment method (optional)",
            ["", *PAYMENT_METHODS],
            format_func=lambda value: value.replace("_", " ").title() if value else "Not specified",
        )

        with st.expander("Optional spending context"):
            col_d, col_e = st.columns(2)
            with col_d:
                is_restaurant = st.checkbox("Restaurant visit")
                meal_type = st.selectbox(
                    "Meal type",
                    ["", *MEAL_TYPES],
                    format_func=lambda value: value.title() if value else "Not specified",
                )
                is_coffee = st.checkbox("Coffee or snack")
            with col_e:
                transport_mode = st.selectbox(
                    "Transport mode",
                    ["", *TRANSPORT_MODES],
                    format_func=lambda value: (
                        value.replace("_", " ").title() if value else "Not specified"
                    ),
                )
                is_shopping = st.checkbox("Shopping")
                is_impulse = st.checkbox("Impulse purchase")

        submitted = st.form_submit_button("Add expense", type="primary", use_container_width=True)

    if not submitted:
        return

    # The form collects a calendar date only, so no timestamp is sent. The
    # backend derives the UTC timestamp for that local day; sending
    # datetime.now() here would contradict the chosen date.
    payload = {
        "amount": f"{amount:.2f}",
        "category": category,
        "expense_date": spent_on.isoformat(),
    }
    if description.strip():
        payload["description"] = description.strip()
    if payment_method:
        payload["payment_method"] = payment_method
    if is_restaurant:
        payload["is_restaurant_visit"] = True
    if meal_type:
        payload["meal_type"] = meal_type
    if is_coffee:
        payload["is_coffee_or_snack"] = True
    if transport_mode:
        payload["transport_mode"] = transport_mode
    if is_shopping:
        payload["is_shopping"] = True
    if is_impulse:
        payload["is_impulse"] = True

    result = call_api(get_client().create_expense, payload)
    if result is not None:
        st.success(f"Added {format_currency(result['amount'])} to {result['category']}.")
        st.rerun()


def _render_history() -> None:
    client = get_client()
    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        date_from = st.date_input("From", value=None, key="exp_filter_from")
    with col_b:
        date_to = st.date_input("To", value=None, key="exp_filter_to")
    with col_c:
        category = st.selectbox(
            "Category",
            ["All", *EXPENSE_CATEGORIES],
            format_func=lambda c: c if c == "All" else c.replace("_", " ").title(),
            key="exp_filter_category",
        )

    if date_from and date_to and date_from > date_to:
        st.error("The start date must not be after the end date.")
        return

    with st.spinner("Loading transactions\u2026"):
        payload = call_api(
            client.list_expenses,
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
            category=None if category == "All" else category,
            limit=200,
        )
    if payload is None:
        return

    items = payload.get("items", [])
    if not items:
        empty_state(
            "No expenses match these filters.", "Try widening the date range.", "\U0001f50d"
        )
        return

    st.caption(f"{payload['total']} transaction(s)")

    for row in items:
        with st.container():
            col_main, col_amount, col_actions = st.columns([4, 2, 3])
            with col_main:
                st.markdown(
                    f"**{row['category'].replace('_', ' ').title()}** \u2014 "
                    f"{row.get('description') or 'No description'}"
                )
                st.caption(format_date(row["expense_date"]))
            with col_amount:
                st.markdown(f"**{format_currency(row['amount'])}**")
            with col_actions:
                edit_key = f"edit_{row['id']}"
                if st.button("Edit", key=f"editbtn_{row['id']}"):
                    st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                if confirm_delete(f"exp_{row['id']}", "Delete"):
                    try:
                        client.delete_expense(row["id"])
                    except ApiError as exc:
                        # Keep the record visible and report the failure honestly.
                        st.error(exc.message)
                        st.session_state.pop(f"confirm_exp_{row['id']}", None)
                    else:
                        st.session_state.pop(f"confirm_exp_{row['id']}", None)
                        set_notice("Expense deleted.")
                        st.rerun()

            if st.session_state.get(edit_key):
                _render_edit_form(row)
            st.divider()


def _render_edit_form(row: dict) -> None:
    with st.form(f"editform_{row['id']}"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            amount = st.number_input(
                "Amount", min_value=0.01, value=float(row["amount"]), format="%.2f"
            )
        with col_b:
            category = st.selectbox(
                "Category",
                EXPENSE_CATEGORIES,
                index=EXPENSE_CATEGORIES.index(row["category"])
                if row["category"] in EXPENSE_CATEGORIES
                else 0,
                format_func=lambda c: c.replace("_", " ").title(),
            )
        with col_c:
            spent_on = st.date_input("Date", value=parse_date(row["expense_date"]))

        description = st.text_input("Description", value=row.get("description") or "")
        saved = st.form_submit_button("Save changes", type="primary")

    if not saved:
        return

    payload = {
        "amount": f"{amount:.2f}",
        "category": category,
        "expense_date": spent_on.isoformat(),
        "description": description.strip() or None,
    }
    result = call_api(get_client().update_expense, row["id"], payload)
    if result is not None:
        st.session_state.pop(f"edit_{row['id']}", None)
        st.success("Expense updated.")
        st.rerun()
