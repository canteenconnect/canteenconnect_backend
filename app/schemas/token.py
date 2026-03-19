"""Authentication token response schemas."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.user import UserRead


class TokenResponse(BaseModel):
    """Bearer token payload returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead

