from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.repository.category_repository import CategoryRepository
from app.schema.category import CategoryOut


class CategoryService:
    def __init__(self, db: Session):
        self.db = db
        self.categories = CategoryRepository(db)

    @staticmethod
    def _to_out(c: models.Category) -> CategoryOut:
        return CategoryOut(id=c.id, name=c.name, product_count=len(c.products))

    def list_categories(self) -> list[CategoryOut]:
        return [self._to_out(c) for c in self.categories.list_all()]

    def create_category(self, name: str) -> CategoryOut:
        if self.categories.get_by_name(name):
            raise HTTPException(status_code=400, detail="Category already exists")
        return self._to_out(self.categories.create(name))

    def delete_category(self, category_id: str) -> None:
        category = self.categories.get_by_id(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        if category.products:
            raise HTTPException(
                status_code=400,
                detail="Move or remove this category's products before deleting it",
            )
        self.categories.delete(category)
