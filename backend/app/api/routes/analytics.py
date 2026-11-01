"""Analytics routes: descriptive summaries and trends. User-scoped."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.ml import analytics
from app.schemas.analytics import (
    BehaviourResponse,
    CategoryItem,
    SummaryResponse,
    TrendsResponse,
    WeekdayItem,
    WeekdayWeekendResponse,
)
from app.services.analytics_service import load_transactions

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=SummaryResponse)
def summary(current_user: CurrentUser, db: DbSession) -> SummaryResponse:
    """Total, average and count statistics for the user's expenses."""
    return SummaryResponse(**analytics.summary(load_transactions(db, current_user)))


@router.get("/categories", response_model=list[CategoryItem])
def categories(current_user: CurrentUser, db: DbSession) -> list[CategoryItem]:
    """Category totals with percentage contributions."""
    breakdown = analytics.category_breakdown(load_transactions(db, current_user))
    return [CategoryItem(**item) for item in breakdown]


@router.get("/trends", response_model=TrendsResponse)
def trends(
    current_user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> TrendsResponse:
    """Daily, weekly and monthly spending trends."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must not be after date_to",
        )
    payload = analytics.trends(load_transactions(db, current_user, date_from, date_to))
    return TrendsResponse(**payload)


@router.get("/weekday-weekend", response_model=WeekdayWeekendResponse)
def weekday_weekend(current_user: CurrentUser, db: DbSession) -> WeekdayWeekendResponse:
    """Compare weekday and weekend spending."""
    return WeekdayWeekendResponse(
        **analytics.weekday_vs_weekend(load_transactions(db, current_user))
    )


@router.get("/weekday-profile", response_model=list[WeekdayItem])
def weekday_profile(current_user: CurrentUser, db: DbSession) -> list[WeekdayItem]:
    """Average spending per day of week."""
    return [
        WeekdayItem(**item) for item in analytics.dow_profile(load_transactions(db, current_user))
    ]


@router.get("/behaviour", response_model=BehaviourResponse)
def behaviour(current_user: CurrentUser, db: DbSession) -> BehaviourResponse:
    """Descriptive spending-behaviour summary."""
    return BehaviourResponse(**analytics.behaviour_summary(load_transactions(db, current_user)))
