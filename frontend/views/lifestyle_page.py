"""Lifestyle tracking: daily check-in and editing previous logs."""

from datetime import date

import streamlit as st

from api_client import ApiError
from app_state import call_api, format_date, get_client, set_notice
from components.ui import confirm_delete, empty_state, hero
from config import SHOPPING_ACTIVITIES, TRANSPORT_MODES, WORK_MODES


def render() -> None:
    """Render the lifestyle page."""
    hero("Lifestyle", "Optional daily context that makes insights possible")

    st.info(
        "These entries are optional. The more days you log, the more reliable the "
        "lifestyle insights become."
    )

    tab_new, tab_history = st.tabs(["Daily check-in", "Previous logs"])
    with tab_new:
        _render_form()
    with tab_history:
        _render_history()


def _render_form() -> None:
    with st.form("lifestyle_form"):
        log_date = st.date_input("Date", value=date.today(), max_value=date.today())

        col_a, col_b = st.columns(2)
        with col_a:
            sleep_hours = st.slider("Sleep hours", 0.0, 12.0, 7.0, 0.5)
            stress_level = st.slider("Stress level (1 calm - 5 high)", 1, 5, 3)
            work_mode = st.selectbox(
                "Work mode",
                ["", *WORK_MODES],
                format_func=lambda v: v.title() if v else "Not specified",
            )
        with col_b:
            commute_mode = st.selectbox(
                "Commute mode",
                ["", *TRANSPORT_MODES],
                format_func=lambda v: v.replace("_", " ").title() if v else "Not specified",
            )
            restaurant_visits = st.number_input("Restaurant visits", 0, 20, 0)
            coffee_snacks = st.number_input("Coffee / snack purchases", 0, 20, 0)

        col_c, col_d = st.columns(2)
        with col_c:
            shopping_activity = st.selectbox(
                "Shopping activity",
                ["", *SHOPPING_ACTIVITIES],
                format_func=lambda v: v.title() if v else "Not specified",
            )
            social_outings = st.number_input("Social outings", 0, 20, 0)
        with col_d:
            exercise = st.checkbox("Exercised today")
            cooked_at_home = st.checkbox("Cooked at home")

        notes = st.text_area("Notes (optional)", max_chars=1000)
        submitted = st.form_submit_button("Save check-in", type="primary", use_container_width=True)

    if not submitted:
        return

    payload = {
        "log_date": log_date.isoformat(),
        "sleep_hours": str(sleep_hours),
        "stress_level": stress_level,
        "restaurant_visits_count": int(restaurant_visits),
        "coffee_snacks_count": int(coffee_snacks),
        "social_outings_count": int(social_outings),
        "exercise": bool(exercise),
        "cooked_at_home": bool(cooked_at_home),
    }
    if work_mode:
        payload["work_mode"] = work_mode
    if commute_mode:
        payload["commute_mode"] = commute_mode
    if shopping_activity:
        payload["shopping_activity"] = shopping_activity
    if notes.strip():
        payload["notes"] = notes.strip()

    result = call_api(get_client().create_lifestyle, payload)
    if result is not None:
        st.success(f"Saved lifestyle log for {format_date(log_date)}.")
        st.rerun()


def _render_history() -> None:
    client = get_client()
    with st.spinner("Loading your lifestyle logs\u2026"):
        payload = call_api(client.list_lifestyle, limit=60)
    if payload is None:
        return

    items = payload.get("items", [])
    if not items:
        empty_state(
            "No lifestyle logs yet",
            "Save a daily check-in to start building lifestyle insights.",
            "\U0001f9d8",
        )
        return

    for row in items:
        with st.container():
            col_main, col_actions = st.columns([5, 2])
            with col_main:
                st.markdown(f"**{format_date(row['log_date'])}**")
                st.caption(_summary_line(row))
            with col_actions:
                edit_key = f"editlog_{row['id']}"
                if st.button("Edit", key=f"editlogbtn_{row['id']}"):
                    st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                if confirm_delete(f"log_{row['id']}", "Delete"):
                    try:
                        client.delete_lifestyle(row["id"])
                    except ApiError as exc:
                        st.error(exc.message)
                        st.session_state.pop(f"confirm_log_{row['id']}", None)
                    else:
                        st.session_state.pop(f"confirm_log_{row['id']}", None)
                        set_notice("Lifestyle log deleted.")
                        st.rerun()

            if st.session_state.get(edit_key):
                _render_edit(row)
            st.divider()


def _summary_line(row: dict) -> str:
    parts = []
    if row.get("sleep_hours") is not None:
        parts.append(f"sleep {row['sleep_hours']}h")
    if row.get("stress_level") is not None:
        parts.append(f"stress {row['stress_level']}/5")
    if row.get("work_mode"):
        parts.append(row["work_mode"])
    if row.get("restaurant_visits_count"):
        parts.append(f"{row['restaurant_visits_count']} restaurant visits")
    if row.get("coffee_snacks_count"):
        parts.append(f"{row['coffee_snacks_count']} coffees/snacks")
    return " \u00b7 ".join(parts) if parts else "No details recorded"


def _render_edit(row: dict) -> None:
    with st.form(f"editlogform_{row['id']}"):
        col_a, col_b = st.columns(2)
        with col_a:
            sleep_hours = st.slider(
                "Sleep hours", 0.0, 12.0, float(row.get("sleep_hours") or 7.0), 0.5
            )
            stress_level = st.slider("Stress level", 1, 5, int(row.get("stress_level") or 3))
        with col_b:
            restaurant_visits = st.number_input(
                "Restaurant visits", 0, 20, int(row.get("restaurant_visits_count") or 0)
            )
            coffee_snacks = st.number_input(
                "Coffee / snack purchases", 0, 20, int(row.get("coffee_snacks_count") or 0)
            )
        notes = st.text_area("Notes", value=row.get("notes") or "", max_chars=1000)
        saved = st.form_submit_button("Save changes", type="primary")

    if not saved:
        return

    payload = {
        "sleep_hours": str(sleep_hours),
        "stress_level": stress_level,
        "restaurant_visits_count": int(restaurant_visits),
        "coffee_snacks_count": int(coffee_snacks),
        "notes": notes.strip() or None,
    }
    result = call_api(get_client().update_lifestyle, row["id"], payload)
    if result is not None:
        st.session_state.pop(f"editlog_{row['id']}", None)
        st.success("Log updated.")
        st.rerun()
