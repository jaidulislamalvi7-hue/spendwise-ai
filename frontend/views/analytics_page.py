"""Analytics: spending behaviour, category analysis and trends."""

import pandas as pd
import streamlit as st

from app_state import call_api, format_currency, format_percent, get_client
from components.ui import category_bar, empty_state, hero, trends_chart


def render() -> None:
    """Render the analytics page."""
    hero("Analytics", "How, when and where your money goes")

    client = get_client()
    with st.spinner("Calculating analytics\u2026"):
        behaviour = call_api(client.behaviour)
        categories = call_api(client.categories)
        trends = call_api(client.trends)
        profile = call_api(client.weekday_profile)

    tab_behaviour, tab_categories, tab_trends = st.tabs(
        ["Spending behaviour", "Category analysis", "Trends"]
    )

    with tab_behaviour:
        _render_behaviour(behaviour, profile)
    with tab_categories:
        _render_categories(categories)
    with tab_trends:
        if not trends or not trends.get("daily"):
            empty_state("No trend data yet.")
        else:
            trends_chart(trends["daily"], "Daily totals")
            col_a, col_b = st.columns(2)
            with col_a:
                trends_chart(trends["weekly"], "Weekly totals")
            with col_b:
                trends_chart(trends["monthly"], "Monthly totals")
            st.caption(f"Overall direction: {trends['trend_direction'].replace('_', ' ')}")


def _render_behaviour(behaviour: dict | None, profile: list[dict] | None) -> None:
    if not behaviour or behaviour.get("no_spend_days") is None:
        empty_state("Not enough data for a behaviour summary.")
        return

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("No-spend days", str(behaviour["no_spend_days"]))
    col_b.metric("Avg transactions / day", f"{behaviour['average_transactions_per_day']:.2f}")
    if behaviour.get("most_frequent_category"):
        col_c.metric(
            "Most frequent category",
            behaviour["most_frequent_category"].replace("_", " ").title(),
        )

    largest_day = behaviour.get("largest_day")
    if largest_day:
        st.caption(
            f"Highest-spend day: {largest_day['date']} at {format_currency(largest_day['total'])}"
        )

    if profile:
        st.subheader("Average spend by weekday")
        frame = pd.DataFrame(profile).rename(columns={"weekday": "Weekday", "average": "Average"})
        st.bar_chart(frame.set_index("Weekday")["Average"], height=260)
        st.caption("Descriptive averages per day of week; not adjusted for seasonality.")


def _render_categories(categories: list[dict] | None) -> None:
    if not categories:
        empty_state("No category data yet.")
        return
    category_bar(categories)
    frame = pd.DataFrame(
        [
            {
                "Category": item["category"].replace("_", " ").title(),
                "Total": format_currency(item["total"]),
                "Share": format_percent(item["percentage"]),
                "Transactions": item["transaction_count"],
                "Average": format_currency(item["average"]),
            }
            for item in categories
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)
