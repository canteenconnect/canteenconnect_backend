"""Registration and session inspection endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession, get_current_active_user
from app.models import User
from app.schemas.token import TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth import authenticate_user, build_token_response, create_user

router = APIRouter()


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a student account",
)
def register_user(db: DbSession, payload: UserCreate) -> UserRead:
    """Register a new student account."""

    try:
        user = create_user(db, payload, allow_admin_role=False)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return user


@router.post("/login", response_model=TokenResponse, summary="Log in with username/password")
def login_user(
    db: DbSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    """Authenticate a user through the auth router."""

    user = authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return build_token_response(user)


@router.get("/me", response_model=UserRead, summary="Return the active user profile")
def read_me(current_user: Annotated[User, Depends(get_current_active_user)]) -> UserRead:
    """Return the currently authenticated user."""

    return current_user

