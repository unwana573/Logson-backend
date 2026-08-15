from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str


class CategoryOut(BaseModel):
    id: str
    name: str
    product_count: int = 0

    class Config:
        from_attributes = True
