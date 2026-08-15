from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import OrderStatus, PaymentMethod


class OrderCreate(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1)
    payment_method: PaymentMethod
    proof_url: Optional[str] = None  # required client-side for manual transfer


class OrderOut(BaseModel):
    id: str
    user_id: str
    user_email: Optional[str] = None
    product_id: str
    product_name: Optional[str] = None
    quantity: int
    amount_kobo: int
    payment_method: PaymentMethod
    status: OrderStatus
    proof_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaystackInitResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str
