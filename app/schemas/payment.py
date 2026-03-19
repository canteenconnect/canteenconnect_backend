"""Schemas for payment tracking."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    """Payload for recording a payment against an order."""

    provider: str = Field(min_length=2, max_length=30)
    transaction_reference: str | None = Field(default=None, max_length=120)
    status: str = Field(default="paid", min_length=4, max_length=20)


class PaymentRead(BaseModel):
    """Serialized payment record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    user_id: int
    provider: str
    amount: Decimal
    status: str
    transaction_reference: str | None
    created_at: datetime
    updated_at: datetime

