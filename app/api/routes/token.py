"""OAuth2 token endpoint used by Swagger UI and clients."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession
from app.schemas.token import TokenResponse
from app.services.auth import authenticate_user, build_token_response

router = APIRouter()


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Issue an OAuth2 access token",
    description=(
        "Primary OAuth2 password-flow endpoint used by Swagger UI and frontend "
        "clients. Submit `application/x-www-form-urlencoded` data with a "
        "`username` field that may contain either the user's username or email, "
        "plus the plaintext `password`."
    ),
)
def issue_token(
    db: DbSession,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    """Authenticate a user and return a bearer token."""

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

