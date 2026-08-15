from typing import Optional

from sqlalchemy.orm import Session

from app import models


class OrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, order_id: str) -> Optional[models.Order]:
        return self.db.query(models.Order).filter(models.Order.id == order_id).first()

    def list_for_user(self, user_id: str) -> list[models.Order]:
        return (
            self.db.query(models.Order)
            .filter(models.Order.user_id == user_id)
            .order_by(models.Order.created_at.desc())
            .all()
        )

    def list_all(self, status: Optional[models.OrderStatus] = None) -> list[models.Order]:
        query = self.db.query(models.Order)
        if status:
            query = query.filter(models.Order.status == status)
        return query.order_by(models.Order.created_at.desc()).all()

    def create(
        self,
        *,
        user_id: str,
        product_id: str,
        quantity: int,
        amount_kobo: int,
        payment_method: models.PaymentMethod,
        proof_url: Optional[str],
    ) -> models.Order:
        order = models.Order(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            amount_kobo=amount_kobo,
            payment_method=payment_method,
            proof_url=proof_url,
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def commit_and_refresh(self, order: models.Order) -> models.Order:
        self.db.commit()
        self.db.refresh(order)
        return order
