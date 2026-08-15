from typing import Optional

from sqlalchemy.orm import Session

from app import models


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def count(self) -> int:
        return self.db.query(models.User).count()

    def get_by_id(self, user_id: str) -> Optional[models.User]:
        return self.db.query(models.User).filter(models.User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[models.User]:
        return self.db.query(models.User).filter(models.User.email == email).first()

    def get_by_google_id(self, google_id: str) -> Optional[models.User]:
        return self.db.query(models.User).filter(models.User.google_id == google_id).first()

    def list_all(self) -> list[models.User]:
        return self.db.query(models.User).order_by(models.User.created_at.asc()).all()

    def create(self, *, full_name: str, email: str, hashed_password: str, is_admin: bool) -> models.User:
        user = models.User(
            full_name=full_name,
            email=email,
            hashed_password=hashed_password,
            is_admin=is_admin,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_google_user(self, *, full_name: str, email: str, google_id: str, is_admin: bool) -> models.User:
        user = models.User(
            full_name=full_name,
            email=email,
            hashed_password=None,
            google_id=google_id,
            is_admin=is_admin,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def attach_google_id(self, user: models.User, google_id: str) -> models.User:
        user.google_id = google_id
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_role(self, user: models.User, is_admin: bool) -> models.User:
        user.is_admin = is_admin
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_status(self, user: models.User, is_active: bool) -> models.User:
        user.is_active = is_active
        self.db.commit()
        self.db.refresh(user)
        return user

    def credit_spend(self, user: models.User, amount_kobo: int) -> None:
        user.amount_spent_kobo += amount_kobo
        # caller is responsible for committing as part of a larger transaction
