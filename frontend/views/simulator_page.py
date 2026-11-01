"""What-if simulator.

Every scenario is direct arithmetic on recorded spending. Model-based estimates
are explicitly reported as unavailable rather than shown as an empty list.
"""

import streamlit as st

from app_state import call_api, format_currency, get_client
from components.ui import caveat, empty_state, hero
from config import EXPENSE_CATEGORIES
from formatting import to_decimal

SCENARIO_LABELS = {
    "taxi_to_bus": "Taxi replaced with bus",
    "reduce_restaurant_visits": "Fewer restaurant visits",
    "reduce_coffee_snacks": "Reduced coffee / snack spending",
    "reduce_category": "Category spending reduced",
    "add_recurring_expense": "New recurring expense",
}


def render() -> None:
    """Render the what-if simulator."""
    hero("What-if simulator", "Explore hypothetical changes to your recorded spending")

    st.info(
        "These scenarios are arithmetic on spending you have already recorded. "
        "They do not predict that you would actually make the change."
    )

    with st.form("simulator_form"):
        st.subheader("Taxi \u2192 bus")
        col_a, col_b = st.columns(2)
        with col_a:
            use_bus = st.checkbox("Replace my taxi/ride-share trips")
        with col_b:
            bus_fare = st.number_input("Bus fare per trip", min_value=0.0, value=1.0, step=0.5)

        st.subheader("Reduce spending")
        col_c, col_d = st.columns(2)
        with col_c:
            restaurant_pct = st.slider("Cut restaurant spending (%)", 0, 100, 0, disabled=False)
        with col_d:
            coffee_pct = st.slider("Cut coffee / snack spending (%)", 0, 100, 0)

        col_e, col_f = st.columns(2)
        with col_e:
            category = st.selectbox(
                "Reduce a category",
                [""] + list(EXPENSE_CATEGORIES),
                format_func=lambda c: c.replace("_", " ").title() if c else "No category",
            )
        with col_f:
            category_pct = st.slider("Category reduction (%)", 0, 100, 0)

        st.subheader("Add a recurring expense")
        col_g, col_h = st.columns(2)
        with col_g:
            recurring_amount = st.number_input(
                "Amount per occurrence", min_value=0.0, value=0.0, step=1.0
            )
        with col_h:
            recurring_times = st.number_input("Times per month", min_value=1, value=1)

        submitted = st.form_submit_button(
            "Run simulation", type="primary", use_container_width=True
        )

    if not submitted:
        return

    payload: dict = {}
    if use_bus:
        payload["bus_fare"] = float(bus_fare)
    if restaurant_pct > 0:
        payload["restaurant_reduction_pct"] = float(restaurant_pct)
    if coffee_pct > 0:
        payload["coffee_reduction_pct"] = float(coffee_pct)
    if category and category_pct > 0:
        payload["category"] = category
        payload["category_reduction_pct"] = float(category_pct)
    if recurring_amount > 0:
        payload["recurring_amount"] = float(recurring_amount)
        payload["recurring_times_per_month"] = int(recurring_times)

    if not payload:
        st.warning("Choose at least one scenario to simulate.")
        return

    result = call_api(get_client().simulate, payload)
    if result is None:
        return

    if result.get("status") != "ok":
        empty_state(
            "No spending history to simulate",
            "Record some expenses first, then come back to try scenarios.",
            "\U0001f9ee",
        )
        return

    window = result.get("window", {})
    st.caption(
        f"Based on {window.get('days')} recorded day(s), "
        f"{window.get('date_from')} to {window.get('date_to')}."
    )

    calculated = result.get("calculated", [])
    if not calculated:
        st.info("No scenario produced a result.")
    for item in calculated:
        label = SCENARIO_LABELS.get(item["scenario"], item["scenario"].replace("_", " ").title())
        with st.expander(label, expanded=True):
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Current", format_currency(item["current_cost"]))
            col_b.metric("Scenario", format_currency(item["scenario_cost"]))
            difference = to_decimal(item["difference"])
            if difference is None:
                col_c.metric("Difference", "\u2014")
            else:
                col_c.metric(
                    "Difference",
                    format_currency(abs(difference)),
                    delta=f"{difference:,.2f}",
                )
            st.caption(item.get("note", ""))
            assumptions = item.get("assumptions") or {}
            if assumptions:
                st.caption(
                    "Assumptions: "
                    + ", ".join(
                        f"{key.replace('_', ' ')}={value}" for key, value in assumptions.items()
                    )
                )
            st.markdown('<span class="sw-badge">calculated</span>', unsafe_allow_html=True)

    st.divider()
    st.subheader("Model-based estimates")
    if result.get("estimated_status") == "unavailable":
        st.warning(result.get("estimated_reason") or "Model-based estimates are unavailable.")
    elif result.get("estimated"):
        for item in result["estimated"]:
            st.write(item)
    else:
        st.info("No model-based estimates were requested.")

    caveat(result.get("caveat", ""))
