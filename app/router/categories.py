from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.config.database import get_db
from app.config.deps import get_current_admin
from app.schema.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.service.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return CategoryService(db).list_categories()


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return CategoryService(db).create_category(payload.name)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: str,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return CategoryService(db).update_category(category_id, payload.name)


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    CategoryService(db).delete_category(category_id)