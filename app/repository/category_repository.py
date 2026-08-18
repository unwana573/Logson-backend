from typing import Optional

from sqlalchemy.orm import Session

from app import models


class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[models.Category]:
        return self.db.query(models.Category).order_by(models.Category.name).all()

    def get_by_id(self, category_id: str) -> Optional[models.Category]:
        return self.db.query(models.Category).filter(models.Category.id == category_id).first()

    def get_by_name(self, name: str) -> Optional[models.Category]:
        return self.db.query(models.Category).filter(models.Category.name == name).first()

    def create(self, name: str) -> models.Category:
        category = models.Category(name=name)
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def update(self, category: models.Category, name: str) -> models.Category:
        category.name = name
        self.db.commit()
        self.db.refresh(category)
        return category

    def delete(self, category: models.Category) -> None:
        self.db.delete(category)
        self.db.commit()