"""Schemas for order placement and status updates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    """Client payload for a single order line item."""

    menu_item_id: int
    quantity: int = Field(ge=1, le=50)


class OrderCreate(BaseModel):
    """Payload for placing a new order."""

    outlet_id: int | None = None
    items: list[OrderItemCreate] = Field(min_length=1)
    payment_method: str = Field(min_length=2, max_length=30, default="cash")


class OrderItemRead(BaseModel):
    """Serialized order item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class OrderRead(BaseModel):
    """Serialized order with nested items."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    student_id: int
    outlet_id: int
    status: str
    payment_status: str
    total_amount: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class OrderStatusUpdate(BaseModel):
    """Payload for updating order fulfillment status."""

    status: str = Field(min_length=3, max_length=20)

