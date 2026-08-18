from typing import Optional

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str
    vendor: str
    description: Optional[str] = None
    category_id: str
    price_kobo: int
    image_url: Optional[str] = None
    stock_text: str = Field(
        default="",
        description="One credential per line. Each line becomes one unit of stock. "
        "Can be left empty and added afterward via POST /products/{id}/stock.",
    )


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    price_kobo: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    id: str
    name: str
    vendor: str
    description: Optional[str] = None
    category_id: str
    category_name: Optional[str] = None
    price_kobo: int
    image_url: Optional[str] = None
    is_active: bool
    stock_count: int

    class Config:
        from_attributes = True


class AddStockRequest(BaseModel):
    stock_text: str = Field(description="One credential per line")