"""Prediction and simulation routes."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.ml import prediction, simulation
from app.ml.features import build_feature_matrix, handle_missing_values
from app.schemas.analytics import (
    FeatureImportanceResponse,
    PredictionResponse,
    SimulationRequest,
    SimulationResponse,
)
from app.services.analytics_service import load_daily_series, load_transactions

router = APIRouter(prefix="/predictions", tags=["predictions"])
simulation_router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get("/daily", response_model=PredictionResponse)
def daily_prediction(current_user: CurrentUser, db: DbSession) -> PredictionResponse:
    """Predict the next day's spending, with evaluation against baselines."""
    payload = prediction.evaluate_and_predict(load_daily_series(db, current_user))
    return PredictionResponse(**payload)


@router.get("/weekly", response_model=PredictionResponse)
def weekly_prediction(current_user: CurrentUser, db: DbSession) -> PredictionResponse:
    """Seven-day spending outlook derived from the daily method."""
    payload = prediction.evaluate_and_predict(load_daily_series(db, current_user))
    payload["caveat"] = (
        "The weekly figure multiplies the daily estimate by seven, so its error "
        "compounds. Treat it as a rough planning figure, not a forecast you can rely on."
    )
    return PredictionResponse(**payload)


@router.get("/feature-importance", response_model=FeatureImportanceResponse)
def feature_importance(current_user: CurrentUser, db: DbSession) -> FeatureImportanceResponse:
    """Rank the features the predictive model relies on."""
    daily = load_daily_series(db, current_user)
    if daily.empty:
        return FeatureImportanceResponse(status="insufficient_data", features=[])
    features = handle_missing_values(build_feature_matrix(daily))
    return FeatureImportanceResponse(**prediction.feature_importance(features))


@simulation_router.post("/what-if", response_model=SimulationResponse)
def what_if(
    payload: SimulationRequest, current_user: CurrentUser, db: DbSession
) -> SimulationResponse:
    """Run what-if scenarios as direct arithmetic on the user's recorded spending."""
    result = simulation.run(
        load_transactions(db, current_user),
        bus_fare=payload.bus_fare,
        restaurant_reduction_pct=payload.restaurant_reduction_pct,
        coffee_reduction_pct=payload.coffee_reduction_pct,
        category=payload.category,
        category_reduction_pct=payload.category_reduction_pct,
        recurring_amount=payload.recurring_amount,
        recurring_times_per_month=payload.recurring_times_per_month,
    )
    return SimulationResponse(**result)
