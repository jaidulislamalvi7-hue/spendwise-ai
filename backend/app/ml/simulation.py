"""What-if simulator.

Two visibly different output classes:
- ``calculated``: arithmetic on the user's own recorded spending;
- ``estimated``: a projection from a fitted model, labelled as such.

The two are never blended, and no output claims that a change *would* produce
these savings.
"""

from typing import Any

import pandas as pd

from app.ml.config import SIMULATION_CAVEAT


def _empty(totals: dict[str, float]) -> dict[str, Any]:
    return {
        "status": "insufficient_data",
        "window": {"days": 0, "date_from": None, "date_to": None},
        "current": totals,
        "calculated": [],
        **_estimates_payload(),
        "caveat": SIMULATION_CAVEAT,
    }


def window_of(transactions: pd.DataFrame) -> dict[str, Any]:
    """Describe the historical window used for a simulation."""
    if transactions.empty:
        return {"days": 0, "date_from": None, "date_to": None}
    dates = pd.to_datetime(transactions["expense_date"])
    return {
        "days": int(dates.dt.date.nunique()),
        "date_from": str(dates.min().date()),
        "date_to": str(dates.max().date()),
    }


def _sum_for(transactions: pd.DataFrame, mask: pd.Series) -> float:
    return round(float(transactions.loc[mask, "amount"].astype(float).sum()), 2)


def taxi_to_bus(
    transactions: pd.DataFrame, bus_fare: float, trips: int | None = None
) -> dict[str, Any]:
    """Replace recorded taxi/ride-share trips with a given bus fare."""
    mask = transactions["transport_mode"].isin(["taxi", "ride_share"])
    taxi_total = _sum_for(transactions, mask)
    trip_count = int(mask.sum()) if trips is None else trips
    new_cost = round(float(bus_fare) * trip_count, 2)
    return {
        "scenario": "taxi_to_bus",
        "classification": "calculated",
        "assumptions": {
            "bus_fare": bus_fare,
            "trips_replaced": trip_count,
            "fare_source": "user-supplied",
        },
        "current_cost": taxi_total,
        "scenario_cost": new_cost,
        "difference": round(taxi_total - new_cost, 2),
        "note": (
            "This is arithmetic on recorded taxi spending. It does not assume you "
            "would actually switch, nor that the bus always costs this fare."
        ),
    }


def reduce_restaurant_visits(transactions: pd.DataFrame, reduction_pct: float) -> dict[str, Any]:
    """Reduce restaurant spending by a percentage."""
    mask = transactions["is_restaurant_visit"].fillna(False).astype(bool)
    current = _sum_for(transactions, mask)
    reduction = max(0.0, min(100.0, float(reduction_pct))) / 100.0
    return _reduction_result(
        "reduce_restaurant_visits",
        current,
        reduction,
        {"reduction_percent": reduction_pct, "matched_transactions": int(mask.sum())},
    )


def reduce_coffee_snacks(transactions: pd.DataFrame, reduction_pct: float) -> dict[str, Any]:
    """Reduce coffee/snack spending by a percentage."""
    mask = transactions["is_coffee_or_snack"].fillna(False).astype(bool)
    current = _sum_for(transactions, mask)
    reduction = max(0.0, min(100.0, float(reduction_pct))) / 100.0
    return _reduction_result(
        "reduce_coffee_snacks",
        current,
        reduction,
        {"reduction_percent": reduction_pct, "matched_transactions": int(mask.sum())},
    )


def reduce_category(
    transactions: pd.DataFrame, category: str, reduction_pct: float
) -> dict[str, Any]:
    """Reduce all spending in one category by a percentage."""
    mask = transactions["category"] == category
    current = _sum_for(transactions, mask)
    reduction = max(0.0, min(100.0, float(reduction_pct))) / 100.0
    return _reduction_result(
        "reduce_category",
        current,
        reduction,
        {
            "category": category,
            "reduction_percent": reduction_pct,
            "matched_transactions": int(mask.sum()),
        },
    )


def _reduction_result(
    scenario: str, current: float, reduction: float, assumptions: dict[str, Any]
) -> dict[str, Any]:
    new_cost = round(current * (1 - reduction), 2)
    return {
        "scenario": scenario,
        "classification": "calculated",
        "assumptions": assumptions,
        "current_cost": current,
        "scenario_cost": new_cost,
        "difference": round(current - new_cost, 2),
        "note": "Direct arithmetic on recorded spending, not a forecast of behaviour change.",
    }


def add_recurring_expense(
    transactions: pd.DataFrame, amount: float, times_per_month: int = 1
) -> dict[str, Any]:
    """Add a hypothetical recurring expense to the observed period."""
    window = window_of(transactions)
    days = max(1, window["days"])
    monthly = round(float(amount) * int(times_per_month), 2)
    current = round(float(transactions["amount"].astype(float).sum()), 2)
    scaled = round(monthly * (days / 30.0), 2)
    return {
        "scenario": "add_recurring_expense",
        "classification": "calculated",
        "assumptions": {
            "amount": amount,
            "times_per_month": times_per_month,
            "monthly_cost": monthly,
            "prorated_over_window": scaled,
        },
        "current_cost": current,
        "scenario_cost": round(current + scaled, 2),
        "difference": round(scaled, 2),
        "note": "Adds the stated cost to the observed period; it is not a prediction.",
    }


def model_estimate(projected_daily: float, window_days: int, basis: str) -> dict[str, Any]:
    """Wrap a model-derived projection as a clearly separate estimate.

    Kept for when a validated prediction path exists; not used by ``run``
    because estimates are deliberately reported as unavailable.
    """
    return {
        "classification": "estimated",
        "projected_daily": round(float(projected_daily), 2),
        "projected_over_window": round(float(projected_daily) * max(1, window_days), 2),
        "basis": basis,
        "caveat": (
            "Model-based estimate. It is shown separately from the calculated figures "
            "and carries model error."
        ),
    }


# Explicit status for the model-based branch.
ESTIMATES_UNAVAILABLE_REASON = (
    "Model-based what-if estimates are not available. A hypothetical change cannot be "
    "fed into the forecasting model in a way that would be validated, so no estimated "
    "figures are produced. The calculated scenarios above are direct arithmetic on "
    "recorded spending."
)


def _estimates_payload() -> dict[str, Any]:
    """Return the explicitly-unavailable estimate block.

    ``estimated`` stays a list so the schema is stable, but ``estimated_status``
    makes the absence explicit rather than implying support with an empty list.
    """
    return {
        "estimated": [],
        "estimated_status": "unavailable",
        "estimated_reason": ESTIMATES_UNAVAILABLE_REASON,
    }


def run(
    transactions: pd.DataFrame,
    *,
    bus_fare: float | None = None,
    restaurant_reduction_pct: float | None = None,
    coffee_reduction_pct: float | None = None,
    category: str | None = None,
    category_reduction_pct: float | None = None,
    recurring_amount: float | None = None,
    recurring_times_per_month: int = 1,
) -> dict[str, Any]:
    """Run the requested scenarios against the user's recorded transactions."""
    totals = {
        "total_spend": round(float(transactions["amount"].astype(float).sum()), 2)
        if not transactions.empty
        else 0.0
    }
    if transactions.empty:
        return _empty(totals)

    calculated: list[dict[str, Any]] = []
    if bus_fare is not None:
        calculated.append(taxi_to_bus(transactions, bus_fare))
    if restaurant_reduction_pct is not None:
        calculated.append(reduce_restaurant_visits(transactions, restaurant_reduction_pct))
    if coffee_reduction_pct is not None:
        calculated.append(reduce_coffee_snacks(transactions, coffee_reduction_pct))
    if category is not None and category_reduction_pct is not None:
        calculated.append(reduce_category(transactions, category, category_reduction_pct))
    if recurring_amount is not None:
        calculated.append(
            add_recurring_expense(transactions, recurring_amount, recurring_times_per_month)
        )

    return {
        "status": "ok",
        "window": window_of(transactions),
        "current": totals,
        "calculated": calculated,
        **_estimates_payload(),
        "caveat": SIMULATION_CAVEAT,
    }
