"""Schemas for menu item CRUD operations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MenuItemCreate(BaseModel):
    """Payload for creating a menu item."""

    outlet_id: int
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price: Decimal = Field(gt=0)
    stock_quantity: int = Field(ge=0, default=0)
    is_available: bool = True


class MenuItemUpdate(BaseModel):
    """Partial update payload for an existing menu item."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price: Decimal | None = Field(default=None, gt=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_available: bool | None = None
    outlet_id: int | None = None


class MenuItemRead(BaseModel):
    """Serialized menu item returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    outlet_id: int
    name: str
    description: str | None
    price: Decimal
    stock_quantity: int
    is_available: bool
    created_at: datetime
    updated_at: datetime

