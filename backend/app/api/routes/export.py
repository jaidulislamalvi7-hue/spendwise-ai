"""User-scoped data export routes (CSV)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.services.export_service import export_expenses_csv, export_lifestyle_csv

router = APIRouter(prefix="/export", tags=["export"])


def _csv_response(content: str, filename: str) -> Response:
    """Return CSV as a download without letting a browser render it inline."""
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/expenses.csv")
def export_expenses(
    current_user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> Response:
    """Download the authenticated user's expenses as CSV."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must not be after date_to",
        )
    content = export_expenses_csv(db, current_user, date_from, date_to)
    return _csv_response(content, "spendwise-expenses.csv")


@router.get("/lifestyle.csv")
def export_lifestyle(
    current_user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> Response:
    """Download the authenticated user's lifestyle logs as CSV."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must not be after date_to",
        )
    content = export_lifestyle_csv(db, current_user, date_from, date_to)
    return _csv_response(content, "spendwise-lifestyle.csv")
