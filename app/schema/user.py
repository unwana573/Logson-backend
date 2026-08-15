from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    is_admin: bool
    is_active: bool
    amount_spent_kobo: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    is_admin: bool


class UserStatusUpdate(BaseModel):
    is_active: bool


class AssignedCredentialOut(BaseModel):
    product_name: str
    vendor: str
    credential: str
    purchased_at: datetime
