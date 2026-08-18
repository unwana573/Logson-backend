from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_filtered(
        self, *, search: Optional[str] = None, category_id: Optional[str] = None
    ) -> list[models.Product]:
        query = self.db.query(models.Product).filter(models.Product.is_active.is_(True))

        if category_id:
            query = query.filter(models.Product.category_id == category_id)

        if search:
            like = f"%{search.strip()}%"
            query = query.filter(
                or_(models.Product.name.ilike(like), models.Product.vendor.ilike(like))
            )

        return query.order_by(models.Product.name).all()

    def get_by_id(self, product_id: str) -> Optional[models.Product]:
        return self.db.query(models.Product).filter(models.Product.id == product_id).first()

    def create(
        self,
        *,
        name: str,
        vendor: str,
        category_id: str,
        price_kobo: int,
        image_url: Optional[str],
        description: Optional[str] = None,
    ) -> models.Product:
        product = models.Product(
            name=name,
            vendor=vendor,
            category_id=category_id,
            price_kobo=price_kobo,
            image_url=image_url,
            description=description,
        )
        self.db.add(product)
        self.db.flush()  # get product.id before adding stock units
        return product

    def update(self, product: models.Product, fields: dict) -> models.Product:
        for field, value in fields.items():
            setattr(product, field, value)
        self.db.commit()
        self.db.refresh(product)
        return product

    def add_stock_lines(self, product: models.Product, lines: list[str]) -> None:
        for line in lines:
            self.db.add(models.StockUnit(product_id=product.id, credential=line))

    def commit_and_refresh(self, product: models.Product) -> models.Product:
        self.db.commit()
        self.db.refresh(product)
        return product

    def available_stock(self, product_id: str, limit: int) -> list[models.StockUnit]:
        return (
            self.db.query(models.StockUnit)
            .filter(models.StockUnit.product_id == product_id, models.StockUnit.is_assigned.is_(False))
            .limit(limit)
            .all()
        )

    def credentials_for_user(self, user_id: str) -> list[models.StockUnit]:
        return (
            self.db.query(models.StockUnit)
            .filter(models.StockUnit.assigned_to_user_id == user_id)
            .all()
        )