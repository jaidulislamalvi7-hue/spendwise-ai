"""Insight routes: correlation, clustering, anomalies and lifestyle relations."""

import pandas as pd
from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.ml import anomaly, clustering, correlation
from app.ml.features import add_lifestyle_features, build_daily_frame
from app.models.user import User
from app.schemas.analytics import (
    AnomalyResponse,
    ClusterResponse,
    CorrelationResponse,
)
from app.services.analytics_service import load_lifestyle, load_transactions

router = APIRouter(prefix="/insights", tags=["insights"])


def _daily_with_lifestyle(db: Session, current_user: User) -> pd.DataFrame:
    """Build a daily frame plus (same-day) lifestyle columns for correlation.

    Same-day alignment is correct here because correlation is descriptive; it is
    never used as a prediction input.
    """
    transactions = load_transactions(db, current_user)
    if transactions.empty:
        return build_daily_frame(transactions["expense_date"], transactions["amount"])
    daily = build_daily_frame(transactions["expense_date"], transactions["amount"])
    lifestyle = load_lifestyle(db, current_user)
    if lifestyle.empty:
        return daily
    return add_lifestyle_features(daily, lifestyle, lag_days=0)


@router.get("/correlations", response_model=CorrelationResponse)
def correlations(current_user: CurrentUser, db: DbSession) -> CorrelationResponse:
    """Lifestyle/spending associations with sample sizes and caveats."""
    payload = correlation.analyse(_daily_with_lifestyle(db, current_user))
    return CorrelationResponse(**payload)


@router.get("/clusters", response_model=ClusterResponse)
def clusters(current_user: CurrentUser, db: DbSession) -> ClusterResponse:
    """Group the user's spending days into descriptive segments."""
    payload = clustering.cluster_days(load_transactions(db, current_user))
    return ClusterResponse(**payload)


@router.get("/anomalies", response_model=AnomalyResponse)
def anomalies(
    current_user: CurrentUser, db: DbSession, include_isolation_forest: bool = False
) -> AnomalyResponse:
    """Flag unusually large transactions with explainable reasons."""
    payload = anomaly.detect(
        load_transactions(db, current_user), include_isolation_forest=include_isolation_forest
    )
    return AnomalyResponse(**payload["primary"])
