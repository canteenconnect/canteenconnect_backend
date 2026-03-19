"""Authentication token response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserRead


class TokenResponse(BaseModel):
    """Bearer token payload returned after successful authentication."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user": {
                    "id": 1,
                    "username": "admin1",
                    "email": "admin1@example.com",
                    "full_name": "Admin One",
                    "role": "admin",
                    "is_active": True,
                    "created_at": "2026-03-19T10:00:00Z",
                    "updated_at": "2026-03-19T10:00:00Z",
                },
            }
        }
    )

    access_token: str = Field(description="Signed JWT access token.")
    token_type: str = Field(default="bearer", description="Token type understood by OAuth2 clients.")
    user: UserRead
