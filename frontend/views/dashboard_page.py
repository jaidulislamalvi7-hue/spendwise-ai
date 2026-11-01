"""Dashboard: headline metrics, trends, category mix and recent transactions."""

from datetime import date

import streamlit as st

from app_state import (
    call_api,
    format_currency,
    format_date,
    format_percent,
    get_client,
)
from components.ui import (
    category_bar,
    empty_state,
    hero,
    metric_row,
    trends_chart,
)


def render() -> None:
    """Render the dashboard."""
    hero("Dashboard", "Your spending at a glance")

    client = get_client()
    with st.spinner("Loading your dashboard\u2026"):
        summary = call_api(client.summary)
        categories = call_api(client.categories)
        trends = call_api(client.trends)
        weekday_weekend = call_api(client.weekday_weekend)
        recent = call_api(client.list_expenses, limit=8)

    if summary is None:
        return

    if summary["transaction_count"] == 0:
        empty_state(
            "No expenses recorded yet",
            "Add your first expense on the Expenses page to unlock your dashboard.",
            "\U0001f4b8",
        )
        return

    metric_row(
        [
            ("Total spending", format_currency(summary["total_spend"]), "All recorded expenses"),
            (
                "Average per calendar day",
                format_currency(summary["average_per_day"]),
                "Spread across every day in the range, including days with no spending",
            ),
            (
                "Transactions",
                str(summary["transaction_count"]),
                f"Largest: {format_currency(summary['largest_transaction'])}",
            ),
            (
                "Median transaction",
                format_currency(summary["median_transaction"]),
                f"Over {summary['days_recorded']} days",
            ),
        ]
    )

    st.caption(
        f"Recorded period: {format_date(summary['date_from'])} \u2013 "
        f"{format_date(summary['date_to'])}"
    )

    # Monthly spending for the current calendar month.
    month_total = _current_month_total(trends)
    if month_total is not None:
        st.metric(
            f"Spending this month ({date.today().strftime('%B %Y')})",
            format_currency(month_total),
        )

    st.divider()
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Trends")
        if trends:
            tab_daily, tab_weekly, tab_monthly = st.tabs(["Daily", "Weekly", "Monthly"])
            with tab_daily:
                trends_chart(trends.get("daily", []), "Daily totals")
            with tab_weekly:
                trends_chart(trends.get("weekly", []), "Weekly totals")
            with tab_monthly:
                trends_chart(trends.get("monthly", []), "Monthly totals")
            direction = trends.get("trend_direction", "insufficient_data").replace("_", " ")
            st.caption(f"Recent direction: {direction}")
    with right:
        st.subheader("By category")
        category_bar(categories or [])
        for item in (categories or [])[:6]:
            st.caption(
                f"{item['category'].replace('_', ' ').title()} \u2014 "
                f"{format_currency(item['total'])} ({format_percent(item['percentage'])})"
            )

    st.divider()
    st.subheader("Weekday vs weekend")
    if weekday_weekend:
        col_a, col_b = st.columns(2)
        col_a.metric("Weekday average", format_currency(weekday_weekend["weekday_average"]))
        col_b.metric("Weekend average", format_currency(weekday_weekend["weekend_average"]))
        difference = weekday_weekend["difference"]
        if difference > 0:
            st.caption(f"Weekends run {format_currency(difference)} higher on average.")
        elif difference < 0:
            st.caption(f"Weekends run {format_currency(abs(difference))} lower on average.")
        else:
            st.caption("Weekday and weekend averages are essentially equal.")

    st.divider()
    st.subheader("Recent transactions")
    rows = (recent or {}).get("items", [])
    if not rows:
        empty_state("No transactions yet.")
    else:
        st.dataframe(
            [
                {
                    "Date": format_date(row["expense_date"]),
                    "Category": row["category"].replace("_", " ").title(),
                    "Description": row.get("description") or "\u2014",
                    "Amount": format_currency(row["amount"]),
                }
                for row in rows
            ],
            use_container_width=True,
            hide_index=True,
        )


def _current_month_total(trends: dict | None) -> float | None:
    """Sum the current month's total from the trends payload."""
    if not trends:
        return None
    prefix = date.today().strftime("%Y-%m")
    for record in trends.get("monthly", []):
        if str(record.get("period", "")).startswith(prefix):
            return record.get("total")
    return None
