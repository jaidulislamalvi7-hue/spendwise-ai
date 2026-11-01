"""Expense routes. Every operation is scoped to the authenticated user."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.constants import EXPENSE_CATEGORY_SET
from app.schemas.expense import ExpenseCreate, ExpenseList, ExpenseRead, ExpenseUpdate
from app.services.expense_service import (
    ExpenseDateConflictError,
    ExpenseNotFoundError,
    create_expense,
    delete_expense,
    get_expense,
    list_expenses,
    update_expense,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create(payload: ExpenseCreate, current_user: CurrentUser, db: DbSession) -> ExpenseRead:
    """Create an expense owned by the authenticated user."""
    try:
        return ExpenseRead.model_validate(create_expense(db, current_user, payload))
    except ExpenseDateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("", response_model=ExpenseList)
def list_all(
    current_user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date | None, Query(description="Inclusive lower bound")] = None,
    date_to: Annotated[date | None, Query(description="Inclusive upper bound")] = None,
    category: Annotated[str | None, Query(description="Expense category")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExpenseList:
    """List the user's expenses, optionally filtered by date range and category."""
    if category is not None and category.lower() not in EXPENSE_CATEGORY_SET:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown category: {category}",
        )
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must not be after date_to",
        )
    items, total = list_expenses(
        db,
        current_user,
        date_from=date_from,
        date_to=date_to,
        category=category,
        limit=limit,
        offset=offset,
    )
    return ExpenseList(
        items=[ExpenseRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{expense_id}", response_model=ExpenseRead)
def read_one(expense_id: UUID, current_user: CurrentUser, db: DbSession) -> ExpenseRead:
    """Return one of the user's expenses."""
    try:
        return ExpenseRead.model_validate(get_expense(db, current_user, expense_id))
    except ExpenseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found"
        ) from exc


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update(
    expense_id: UUID, payload: ExpenseUpdate, current_user: CurrentUser, db: DbSession
) -> ExpenseRead:
    """Update one of the user's expenses (partial update)."""
    try:
        return ExpenseRead.model_validate(update_expense(db, current_user, expense_id, payload))
    except ExpenseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found"
        ) from exc
    except ExpenseDateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(expense_id: UUID, current_user: CurrentUser, db: DbSession) -> Response:
    """Delete one of the user's expenses."""
    try:
        delete_expense(db, current_user, expense_id)
    except ExpenseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
