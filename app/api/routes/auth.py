"""Registration and session inspection endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession, TokenDependency, get_current_active_user
from app.models import User
from app.schemas.token import LogoutRequest, RefreshTokenRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth import (
    AuthenticationError,
    authenticate_user,
    build_token_response,
    create_user,
    logout_user,
    rotate_refresh_token,
)

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


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in with username/password",
    description=(
        "Convenience auth route that mirrors the OAuth2 token endpoint. Accepts "
        "`application/x-www-form-urlencoded` credentials and returns the same JWT "
        "bearer token payload as `/token`."
    ),
)
def login_user(
    db: DbSession,
    request: Request,
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
    return build_token_response(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate a refresh token",
)
def refresh_user_session(
    db: DbSession,
    request: Request,
    payload: RefreshTokenRequest,
) -> TokenResponse:
    """Rotate the current refresh token and return a fresh token pair."""

    try:
        return rotate_refresh_token(
            db,
            payload.refresh_token,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current session",
)
def logout_current_session(
    db: DbSession,
    token: TokenDependency,
    payload: LogoutRequest,
) -> Response:
    """Revoke the current access token and the associated refresh family."""

    try:
        logout_user(db, token, refresh_token=payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead, summary="Return the active user profile")
def read_me(current_user: Annotated[User, Depends(get_current_active_user)]) -> UserRead:
    """Return the currently authenticated user."""

    return current_user

