from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str
    roll_number: Optional[str] = None
    department: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class WalletTopupRequest(BaseModel):
    amount: Decimal = Field(gt=0)


class OrderItemInput(BaseModel):
    menu_item_id: int
    quantity: int = Field(gt=0)


class PlaceOrderRequest(BaseModel):
    outlet_id: Optional[int] = None
    payment_mode: str
    items: List[OrderItemInput]


class UpdateOrderStatusRequest(BaseModel):
    status: str


class CreateOutletRequest(BaseModel):
    name: str
    location: str
    is_active: bool = True


class UpdateOutletRequest(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None


class CreateMenuItemRequest(BaseModel):
    outlet_id: int
    item_name: str
    description: Optional[str] = None
    price: Decimal = Field(gt=0)
    available_quantity: int = Field(ge=0)
    is_available: bool = True


class UpdateMenuItemRequest(BaseModel):
    outlet_id: Optional[int] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, gt=0)
    available_quantity: Optional[int] = Field(default=None, ge=0)
    is_available: Optional[bool] = None


class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str
    roll_number: Optional[str] = None
    department: Optional[str] = None


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    roll_number: Optional[str] = None
    department: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    values: dict[str, str]


class APIResponse(BaseModel):
    success: bool = True
    message: str = "ok"
    data: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)