"""Budget routes, scoped to the authenticated user."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.budget import BudgetRead, BudgetStatus, BudgetUpsert
from app.services.budget_service import (
    BudgetNotFoundError,
    delete_budget,
    get_budget,
    status_for,
    status_list,
    upsert_budget,
)

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetStatus])
def list_all(current_user: CurrentUser, db: DbSession) -> list[BudgetStatus]:
    """Return every budget with this month's spending applied."""
    return status_list(db, current_user)


@router.put("", response_model=BudgetRead)
def upsert(payload: BudgetUpsert, current_user: CurrentUser, db: DbSession) -> BudgetRead:
    """Create or update the budget for a category (omit category for overall)."""
    return BudgetRead.model_validate(upsert_budget(db, current_user, payload))


@router.get("/{budget_id}", response_model=BudgetStatus)
def read_one(budget_id: UUID, current_user: CurrentUser, db: DbSession) -> BudgetStatus:
    """Return one budget with its current status."""
    try:
        return status_for(db, current_user, get_budget(db, current_user, budget_id))
    except BudgetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found"
        ) from exc


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(budget_id: UUID, current_user: CurrentUser, db: DbSession) -> Response:
    """Delete one of the user's budgets."""
    try:
        delete_budget(db, current_user, budget_id)
    except BudgetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
