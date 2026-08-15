from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.repository.product_repository import ProductRepository
from app.repository.user_repository import UserRepository
from app.schema.user import AssignedCredentialOut


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.products = ProductRepository(db)

    def list_users(self) -> list[models.User]:
        return self.users.list_all()

    def set_role(self, *, acting_admin: models.User, target_user_id: str, is_admin: bool) -> models.User:
        # The caller reaching this method has already been proven to be an
        # admin by the get_current_admin dependency at the router layer.
        # This method just adds the one extra guardrail an admin can't
        # bypass through the UI: you can't strip your own admin access.
        target = self.users.get_by_id(target_user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if target.id == acting_admin.id and not is_admin:
            raise HTTPException(status_code=400, detail="You can't remove your own admin access")
        return self.users.set_role(target, is_admin)

    def set_status(self, *, acting_admin: models.User, target_user_id: str, is_active: bool) -> models.User:
        target = self.users.get_by_id(target_user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if target.id == acting_admin.id and not is_active:
            raise HTTPException(status_code=400, detail="You can't deactivate your own account")
        return self.users.set_status(target, is_active)

    def my_credentials(self, user_id: str) -> list[AssignedCredentialOut]:
        units = self.products.credentials_for_user(user_id)
        return [
            AssignedCredentialOut(
                product_name=u.product.name,
                vendor=u.product.vendor,
                credential=u.credential,
                purchased_at=u.assigned_at,
            )
            for u in units
        ]
