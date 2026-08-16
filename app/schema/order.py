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


class PagaInitResponse(BaseModel):
    reference: str
    web_payment_link: Optional[str] = None
    bank_transfer_account_number: Optional[str] = None
    ussd_short_code: Optional[str] = None
    expiry_datetime_utc: Optional[str] = None