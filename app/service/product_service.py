from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.repository.category_repository import CategoryRepository
from app.repository.product_repository import ProductRepository
from app.schema.product import ProductCreate, ProductOut, ProductUpdate


class ProductService:
    def __init__(self, db: Session):
        self.db = db
        self.products = ProductRepository(db)
        self.categories = CategoryRepository(db)

    @staticmethod
    def _to_out(p: models.Product) -> ProductOut:
        return ProductOut(
            id=p.id,
            name=p.name,
            vendor=p.vendor,
            description=p.description,
            category_id=p.category_id,
            category_name=p.category.name if p.category else None,
            price_kobo=p.price_kobo,
            image_url=p.image_url,
            is_active=p.is_active,
            stock_count=p.stock_count,
        )

    @staticmethod
    def _parse_stock_lines(stock_text: str) -> list[str]:
        """One credential per line -- this is what turns the admin's bulk
        textarea into individual purchasable stock units."""
        return [line.strip() for line in stock_text.splitlines() if line.strip()]

    def list_products(self, *, search: Optional[str], category_id: Optional[str]) -> list[ProductOut]:
        products = self.products.list_filtered(search=search, category_id=category_id)
        return [self._to_out(p) for p in products]

    def get_product(self, product_id: str) -> ProductOut:
        product = self.products.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return self._to_out(product)

    def create_product(self, payload: ProductCreate) -> ProductOut:
        category = self.categories.get_by_id(payload.category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        product = self.products.create(
            name=payload.name,
            vendor=payload.vendor,
            category_id=payload.category_id,
            price_kobo=payload.price_kobo,
            image_url=payload.image_url,
            description=payload.description,
        )
        self.products.add_stock_lines(product, self._parse_stock_lines(payload.stock_text))
        product = self.products.commit_and_refresh(product)
        return self._to_out(product)

    def update_product(self, product_id: str, payload: ProductUpdate) -> ProductOut:
        product = self.products.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        product = self.products.update(product, payload.model_dump(exclude_unset=True))
        return self._to_out(product)

    def add_stock(self, product_id: str, stock_text: str) -> ProductOut:
        product = self.products.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        self.products.add_stock_lines(product, self._parse_stock_lines(stock_text))
        product = self.products.commit_and_refresh(product)
        return self._to_out(product)