"""Authentication routes: registration, login and profile."""

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.schemas.user import (
    AccountDeleteRequest,
    PasswordChange,
    TokenResponse,
    UserLogin,
    UserRead,
    UserRegister,
    UserUpdate,
)
from app.security.tokens import create_access_token
from app.services.user_service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    authenticate_user,
    change_password,
    delete_account,
    register_user,
    update_profile,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: DbSession) -> UserRead:
    """Create an account. Passwords are stored as Argon2 hashes only."""
    try:
        user = register_user(db, payload)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: DbSession) -> TokenResponse:
    """Exchange credentials for a short-lived access token."""
    user = authenticate_user(db, str(payload.email), payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    settings = get_settings()
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.get("/me", response_model=UserRead)
def read_me(current_user: CurrentUser) -> UserRead:
    """Return the authenticated user's profile."""
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
def update_me(payload: UserUpdate, current_user: CurrentUser, db: DbSession) -> UserRead:
    """Update the authenticated user's profile.

    Changing the timezone only affects how future date-only entries resolve;
    stored UTC timestamps and existing expense dates are never rewritten.
    """
    changes = payload.model_dump(exclude_unset=True)
    user = update_profile(db, current_user, changes)
    return UserRead.model_validate(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: PasswordChange, current_user: CurrentUser, db: DbSession
) -> Response:
    """Change the password after verifying the current one."""
    try:
        change_password(db, current_user, payload.current_password, payload.new_password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    payload: AccountDeleteRequest, current_user: CurrentUser, db: DbSession
) -> Response:
    """Permanently delete the authenticated account and all owned records.

    This is a POST (never a GET) and requires the account password plus an
    explicit ``DELETE`` confirmation, so a leaked token alone cannot destroy
    the account.
    """
    if payload.confirm.strip().upper() != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="confirmation must be the string DELETE",
        )
    try:
        delete_account(db, current_user, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password is incorrect"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
