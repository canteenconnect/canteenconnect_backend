"""Schemas for outlet management."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OutletCreate(BaseModel):
    """Payload for creating or updating an outlet."""

    name: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=255)
    is_active: bool = True


class OutletRead(BaseModel):
    """Serialized outlet data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

