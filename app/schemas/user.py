"""User-facing request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Payload for creating a new application user."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "student1",
                "email": "student1@example.com",
                "full_name": "Student One",
                "password": "StrongPass123!",
                "role": "student",
            }
        }
    )

    username: str = Field(min_length=3, max_length=50, description="Unique login username.")
    email: EmailStr = Field(description="Unique email address used for login or notifications.")
    full_name: str = Field(min_length=2, max_length=120, description="Display name for the user.")
    password: str = Field(min_length=8, max_length=128, description="Plaintext password that will be hashed server-side.")
    role: str = Field(default="student", description="Requested role. Public registration defaults to student.")


class UserRead(BaseModel):
    """Serialized user returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """Payload for admin-managed user updates."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: str | None = Field(default=None, min_length=2, max_length=50)
    is_active: bool | None = None

