"""Predictions: daily/weekly forecasts, baseline comparison and importance."""

import pandas as pd
import streamlit as st

from app_state import call_api, format_currency, get_client
from components.ui import caveat, empty_state, hero


def render() -> None:
    """Render the predictions page."""
    hero("Predictions", "What your past spending suggests about the near future")

    client = get_client()
    with st.spinner("Evaluating models against baselines\u2026"):
        daily = call_api(client.prediction_daily)
        weekly = call_api(client.prediction_weekly)
        importance = call_api(client.feature_importance)

    if daily is None:
        return

    if daily.get("status") != "ok":
        empty_state(
            "Not enough history for a forecast",
            daily.get("message") or "Keep recording expenses to unlock predictions.",
            "\U0001f52e",
        )
        if daily.get("min_days_required"):
            st.caption(
                f"Available: {daily.get('days_available', 0)} days \u00b7 "
                f"required: {daily['min_days_required']} days"
            )
        return

    col_a, col_b = st.columns(2)
    col_a.metric("Next-day forecast", format_currency(daily["next_day_forecast"]))
    col_b.metric("Next 7 days", format_currency(weekly["weekly_forecast"] if weekly else None))

    st.caption(
        f"Method: {daily.get('method')} ({daily.get('method_type', '').replace('_', ' ')}) \u00b7 "
        f"source: {daily.get('forecast_source', 'unknown')}"
    )
    if daily.get("caveat"):
        caveat(daily["caveat"])

    if daily.get("model_rejected_reason"):
        st.info(daily["model_rejected_reason"])
    if daily.get("model_skipped_reason"):
        st.info(daily["model_skipped_reason"])

    st.divider()
    st.subheader("Baseline vs model performance")
    evaluation = daily.get("evaluation") or {}
    baselines = evaluation.get("baselines", {})
    if baselines:
        rows = [
            {
                "Method": name.replace("_", " ").title(),
                "MAE": f"{metrics['mae']:.2f}",
                "RMSE": f"{metrics['rmse']:.2f}",
                "Selected": "yes" if name == evaluation.get("best_baseline") else "",
            }
            for name, metrics in baselines.items()
        ]
        model_metrics = evaluation.get("model")
        if model_metrics:
            rows.append(
                {
                    "Method": "Gradient boosting (model)",
                    "MAE": f"{model_metrics['mae']:.2f}",
                    "RMSE": f"{model_metrics['rmse']:.2f}",
                    "Selected": "yes" if daily.get("method_type") == "model" else "",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            f"Evaluated on the final {daily.get('holdout_days')} day(s) only, in "
            "time order. A model is used only when it beats every baseline on both "
            "MAE and RMSE."
        )

    st.divider()
    st.subheader("What drives the model")
    if not importance or importance.get("status") != "ok" or not importance.get("features"):
        st.info(
            "Feature importance is only available once enough history exists "
            "for a model to be trained."
        )
        return

    frame = pd.DataFrame(importance["features"]).rename(
        columns={"feature": "Feature", "importance": "Importance"}
    )
    st.bar_chart(frame.set_index("Feature")["Importance"], height=300)
    if importance.get("caveat"):
        caveat(importance["caveat"])
