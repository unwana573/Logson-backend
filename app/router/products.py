from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.config.database import get_db
from app.config.deps import get_current_admin
from app.schema.product import AddStockRequest, ProductCreate, ProductOut, ProductUpdate
from app.service.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    search: Optional[str] = None,
    category_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Powers the dashboard search bar: `search` matches product name or
    vendor, case-insensitively."""
    return ProductService(db).list_products(search=search, category_id=category_id)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    return ProductService(db).get_product(product_id)


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return ProductService(db).create_product(payload)


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return ProductService(db).update_product(product_id, payload)


@router.post("/{product_id}/stock", response_model=ProductOut)
def add_stock(
    product_id: str,
    payload: AddStockRequest,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return ProductService(db).add_stock(product_id, payload.stock_text)
