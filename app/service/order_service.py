from datetime import datetime
from typing import Optional

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.config.settings import get_settings
from app.repository.order_repository import OrderRepository
from app.repository.product_repository import ProductRepository
from app.repository.user_repository import UserRepository
from app.schema.order import OrderCreate, OrderOut, PaystackInitResponse

settings = get_settings()


class OrderService:
    def __init__(self, db: Session):
        self.db = db
        self.orders = OrderRepository(db)
        self.products = ProductRepository(db)
        self.users = UserRepository(db)

    @staticmethod
    def _to_out(o: models.Order) -> OrderOut:
        return OrderOut(
            id=o.id,
            user_id=o.user_id,
            user_email=o.user.email if o.user else None,
            product_id=o.product_id,
            product_name=o.product.name if o.product else None,
            quantity=o.quantity,
            amount_kobo=o.amount_kobo,
            payment_method=o.payment_method,
            status=o.status,
            proof_url=o.proof_url,
            created_at=o.created_at,
        )

    def _assign_stock_and_credit(self, order: models.Order) -> None:
        """Fires once an order is confirmed paid, whichever payment method
        got it there: hands out `quantity` unused stock units to the buyer
        and adds the order total to their running amount-spent figure --
        the number the frontend shows instead of a wallet balance."""
        available = self.products.available_stock(order.product_id, limit=order.quantity)
        if len(available) < order.quantity:
            raise HTTPException(status_code=409, detail="Not enough stock left to fulfil this order")

        for unit in available:
            unit.is_assigned = True
            unit.assigned_to_user_id = order.user_id
            unit.assigned_at = datetime.utcnow()

        order.status = models.OrderStatus.success
        order.fulfilled_at = datetime.utcnow()
        self.users.credit_spend(order.user, order.amount_kobo)

    def create_order(self, user: models.User, payload: OrderCreate) -> OrderOut:
        product = self.products.get_by_id(payload.product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=404, detail="Product not found")
        if product.stock_count < payload.quantity:
            raise HTTPException(status_code=409, detail="Not enough stock available")

        if payload.payment_method == models.PaymentMethod.manual and not payload.proof_url:
            raise HTTPException(
                status_code=400,
                detail="A proof-of-payment upload is required for manual bank transfer",
            )

        order = self.orders.create(
            user_id=user.id,
            product_id=product.id,
            quantity=payload.quantity,
            amount_kobo=product.price_kobo * payload.quantity,
            payment_method=payload.payment_method,
            proof_url=payload.proof_url,
        )
        return self._to_out(order)

    def paystack_init(self, order_id: str, user: models.User) -> PaystackInitResponse:
        order = self.orders.get_by_id(order_id)
        if not order or order.user_id != user.id:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.payment_method != models.PaymentMethod.paystack:
            raise HTTPException(status_code=400, detail="This order was not created for Paystack")
        if not settings.PAYSTACK_SECRET_KEY:
            raise HTTPException(status_code=500, detail="PAYSTACK_SECRET_KEY is not configured on the server")

        resp = requests.post(
            f"{settings.PAYSTACK_BASE_URL}/transaction/initialize",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            json={
                "email": user.email,
                "amount": order.amount_kobo,
                "metadata": {"order_id": order.id},
            },
            timeout=15,
        )
        data = resp.json()
        if not data.get("status"):
            raise HTTPException(status_code=502, detail="Could not start Paystack transaction")

        order.paystack_reference = data["data"]["reference"]
        self.orders.commit_and_refresh(order)

        return PaystackInitResponse(
            authorization_url=data["data"]["authorization_url"],
            access_code=data["data"]["access_code"],
            reference=data["data"]["reference"],
        )

    def paystack_verify(self, order_id: str, user: models.User) -> OrderOut:
        order = self.orders.get_by_id(order_id)
        if not order or order.user_id != user.id:
            raise HTTPException(status_code=404, detail="Order not found")
        if not order.paystack_reference:
            raise HTTPException(status_code=400, detail="No Paystack transaction to verify")
        if not settings.PAYSTACK_SECRET_KEY:
            raise HTTPException(status_code=500, detail="PAYSTACK_SECRET_KEY is not configured on the server")

        resp = requests.get(
            f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{order.paystack_reference}",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            timeout=15,
        )
        data = resp.json()
        if data.get("status") and data["data"]["status"] == "success":
            self._assign_stock_and_credit(order)
        else:
            order.status = models.OrderStatus.failed

        order = self.orders.commit_and_refresh(order)
        return self._to_out(order)

    def my_orders(self, user_id: str) -> list[OrderOut]:
        return [self._to_out(o) for o in self.orders.list_for_user(user_id)]

    def list_all(self, status: Optional[models.OrderStatus]) -> list[OrderOut]:
        return [self._to_out(o) for o in self.orders.list_all(status)]

    def approve_manual_order(self, order_id: str) -> OrderOut:
        """Admin approves a manual bank transfer after checking the
        uploaded proof of payment. Paystack orders confirm themselves via
        paystack_verify() instead -- this path is manual-only."""
        order = self.orders.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.payment_method != models.PaymentMethod.manual:
            raise HTTPException(status_code=400, detail="Only manual transfer orders need approval")
        if order.status != models.OrderStatus.pending:
            raise HTTPException(status_code=400, detail="This order has already been processed")

        self._assign_stock_and_credit(order)
        order = self.orders.commit_and_refresh(order)
        return self._to_out(order)

    def reject_order(self, order_id: str) -> OrderOut:
        order = self.orders.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.status != models.OrderStatus.pending:
            raise HTTPException(status_code=400, detail="This order has already been processed")

        order.status = models.OrderStatus.failed
        order = self.orders.commit_and_refresh(order)
        return self._to_out(order)
