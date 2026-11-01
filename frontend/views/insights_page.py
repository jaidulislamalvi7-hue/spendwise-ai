"""Insights: lifestyle correlations, spending clusters and unusual expenses.

Correlation is presented as association only. Sample sizes and caveats are
always shown, and results below the backend's minimum are suppressed.
"""

import pandas as pd
import streamlit as st

from app_state import call_api, format_currency, format_date, get_client
from components.ui import caveat, empty_state, hero

METRIC_LABELS = {
    "sleep_hours_vs_daily_spend": "Sleep hours vs daily spend",
    "stress_vs_daily_spend": "Stress level vs daily spend",
    "restaurant_visits_vs_daily_spend": "Restaurant visits vs daily spend",
    "coffee_snacks_vs_daily_spend": "Coffee/snacks vs daily spend",
    "social_outings_vs_daily_spend": "Social outings vs daily spend",
    "weekend_vs_daily_spend": "Weekend vs weekday spend",
    "cooked_at_home_vs_daily_spend": "Cooked at home vs daily spend",
    "exercise_vs_daily_spend": "Exercise vs daily spend",
}


def render() -> None:
    """Render the insights page."""
    hero("Insights", "Patterns in your spending and lifestyle")

    tab_corr, tab_clusters, tab_anomalies = st.tabs(
        ["Lifestyle correlations", "Spending clusters", "Unusual expenses"]
    )
    with tab_corr:
        _render_correlations()
    with tab_clusters:
        _render_clusters()
    with tab_anomalies:
        _render_anomalies()


def _render_correlations() -> None:
    with st.spinner("Analysing lifestyle relationships\u2026"):
        payload = call_api(get_client().correlations)
    if payload is None:
        return

    caveat(payload["caveat"])

    results = payload.get("results", [])
    if not results:
        empty_state(
            "Not enough lifestyle data yet",
            "Log a few weeks of daily check-ins and lifestyle relationships will appear here.",
            "\U0001f9ea",
        )
        return

    st.caption(
        f"At least {payload['min_pairs_required']} paired days are required. "
        f"Below {payload['caution_below_pairs']} pairs, treat results with extra caution."
    )

    rows = []
    for item in results:
        rows.append(
            {
                "Relationship": METRIC_LABELS.get(item["metric"], item["metric"]),
                "Method": item["method"],
                "Correlation": (
                    f"{item['coefficient']:+.3f}"
                    if item["coefficient"] is not None
                    else "suppressed"
                ),
                "Direction": item["direction"] or "\u2014",
                "Strength": item["strength"] or "\u2014",
                "Days paired": item["sample_size"],
                "Status": "sufficient" if item["sufficient"] else item.get("note", "insufficient"),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    insufficient = [item for item in results if not item["sufficient"]]
    if insufficient:
        st.info(
            f"{len(insufficient)} relationship(s) were suppressed for insufficient data "
            "rather than shown as a misleading number."
        )
    if any(item["caution"] for item in results if item["sufficient"]):
        st.warning("Some pairs have fewer observations than the caution threshold.")


def _render_clusters() -> None:
    with st.spinner("Grouping your spending days\u2026"):
        payload = call_api(get_client().clusters)
    if payload is None:
        return

    if payload["status"] != "ok" or not payload.get("clusters"):
        reason = (
            payload.get("note")
            or payload.get("silhouette_note")
            or "There are not enough recorded days to form meaningful groups."
        )
        empty_state("Clusters unavailable", reason, "\U0001f4ca")
        if payload.get("min_days_required"):
            st.caption(f"At least {payload['min_days_required']} recorded days are required.")
        return

    caveat(payload["caveat"])
    col_a, col_b = st.columns(2)
    col_a.metric("Groups found", str(payload.get("k")))
    col_b.metric("Silhouette score", f"{payload.get('silhouette', 0):.3f}")
    st.caption(payload.get("silhouette_note", ""))

    for cluster in payload["clusters"]:
        with st.expander(
            f"{cluster['label'].title()} \u2014 {cluster['days']} days", expanded=False
        ):
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Average spend", format_currency(cluster["average_total"]))
            col_b.metric("Avg transactions", f"{cluster['average_transactions']:.1f}")
            col_c.metric("Weekend share", f"{cluster['weekend_share'] * 100:.0f}%")
            if cluster["traits"]:
                st.caption("Traits: " + ", ".join(cluster["traits"]))
            st.caption(
                f"Average largest transaction: "
                f"{format_currency(cluster['average_largest_transaction'])}"
            )


def _render_anomalies() -> None:
    with st.spinner("Checking for unusual expenses\u2026"):
        payload = call_api(get_client().anomalies)
    if payload is None:
        return

    caveat(payload["caveat"])

    if payload["status"] != "ok":
        empty_state("Not enough history yet", payload["caveat"], "\U0001f50e")
        return

    flagged = payload.get("flagged", [])
    st.caption(f"Checked {payload['checked']} transactions using a robust median/MAD rule.")

    if not flagged:
        st.success("No unusually large expenses found in your history.")
        return

    for item in flagged:
        category_label = item["category"].replace("_", " ").title()
        with st.expander(
            f"{format_currency(item['amount'])} \u00b7 {category_label} "
            f"\u00b7 {format_date(item['expense_date'])}"
        ):
            st.write(item["reason"])
            if item.get("category_median") is not None:
                typical = format_currency(item["category_median"])
                st.caption(f"Typical for this category: {typical}")
            if item.get("robust_z") is not None:
                st.caption(f"Robust z-score: {item['robust_z']:.2f}")
