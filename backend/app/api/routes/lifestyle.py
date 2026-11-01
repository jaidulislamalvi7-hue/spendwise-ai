"""Lifestyle log routes, scoped to the authenticated user."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.lifestyle import (
    LifestyleLogCreate,
    LifestyleLogList,
    LifestyleLogRead,
    LifestyleLogUpdate,
)
from app.services.lifestyle_service import (
    DuplicateLifestyleLogError,
    LifestyleLogNotFoundError,
    create_lifestyle_log,
    delete_lifestyle_log,
    list_lifestyle_logs,
    update_lifestyle_log,
)

router = APIRouter(prefix="/lifestyle-logs", tags=["lifestyle"])


@router.post("", response_model=LifestyleLogRead, status_code=status.HTTP_201_CREATED)
def create(
    payload: LifestyleLogCreate, current_user: CurrentUser, db: DbSession
) -> LifestyleLogRead:
    """Create a daily lifestyle log (one per user per date)."""
    try:
        log = create_lifestyle_log(db, current_user, payload)
    except DuplicateLifestyleLogError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A lifestyle log already exists for {payload.log_date}",
        ) from exc
    return LifestyleLogRead.model_validate(log)


@router.get("", response_model=LifestyleLogList)
def list_all(
    current_user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=365)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LifestyleLogList:
    """List the user's lifestyle logs."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must not be after date_to",
        )
    items, total = list_lifestyle_logs(
        db, current_user, date_from=date_from, date_to=date_to, limit=limit, offset=offset
    )
    return LifestyleLogList(
        items=[LifestyleLogRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{log_id}", response_model=LifestyleLogRead)
def update(
    log_id: UUID, payload: LifestyleLogUpdate, current_user: CurrentUser, db: DbSession
) -> LifestyleLogRead:
    """Update one of the user's lifestyle logs."""
    try:
        return LifestyleLogRead.model_validate(
            update_lifestyle_log(db, current_user, log_id, payload)
        )
    except LifestyleLogNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lifestyle log not found"
        ) from exc


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(log_id: UUID, current_user: CurrentUser, db: DbSession) -> Response:
    """Delete one of the user's lifestyle logs."""
    try:
        delete_lifestyle_log(db, current_user, log_id)
    except LifestyleLogNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lifestyle log not found"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
