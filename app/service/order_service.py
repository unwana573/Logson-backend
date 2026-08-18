from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.config.settings import get_settings
from app.repository.order_proof_repository import OrderProofRepository
from app.repository.order_repository import OrderRepository
from app.repository.product_repository import ProductRepository
from app.repository.user_repository import UserRepository
from app.schema.order import OrderCreate, OrderOut, PagaInitResponse
from app.service import paga_service

settings = get_settings()


class OrderService:
    def __init__(self, db: Session):
        self.db = db
        self.orders = OrderRepository(db)
        self.products = ProductRepository(db)
        self.users = UserRepository(db)
        self.proofs = OrderProofRepository(db)

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
            has_proof=o.proof is not None,
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

        # A manual transfer's proof is uploaded in a second step
        # (POST /orders/{id}/proof) and enforced at approval time, so
        # creating the order itself no longer requires it.
        order = self.orders.create(
            user_id=user.id,
            product_id=product.id,
            quantity=payload.quantity,
            amount_kobo=product.price_kobo * payload.quantity,
            payment_method=payload.payment_method,
        )
        return self._to_out(order)

    def save_proof(
        self, order_id: str, user: models.User, *, image: bytes, content_type: str
    ) -> OrderOut:
        """Owner uploads (or replaces) the proof-of-payment image for their
        own manual-transfer order while it's still pending. Paga orders and
        already-processed orders don't take a proof."""
        order = self.orders.get_by_id(order_id)
        if not order or order.user_id != user.id:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.payment_method != models.PaymentMethod.manual:
            raise HTTPException(
                status_code=400,
                detail="Proof of payment only applies to manual bank transfer orders",
            )
        if order.status != models.OrderStatus.pending:
            raise HTTPException(status_code=400, detail="This order has already been processed")

        self.proofs.upsert(order_id=order.id, image=image, content_type=content_type)
        order = self.orders.commit_and_refresh(order)
        return self._to_out(order)

    def get_proof(self, order_id: str, user: models.User) -> models.OrderProof:
        """Returns the stored proof image for viewing. The order's owner or
        any admin may fetch it; everyone else gets a 404 that doesn't reveal
        whether the order exists."""
        order = self.orders.get_by_id(order_id)
        if not order or (order.user_id != user.id and not user.is_admin):
            raise HTTPException(status_code=404, detail="Order not found")

        proof = self.proofs.get_by_order_id(order_id)
        if not proof:
            raise HTTPException(status_code=404, detail="No proof of payment uploaded for this order")
        return proof

    def paga_init(self, order_id: str, user: models.User) -> PagaInitResponse:
        order = self.orders.get_by_id(order_id)
        if not order or order.user_id != user.id:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.payment_method != models.PaymentMethod.paga:
            raise HTTPException(status_code=400, detail="This order was not created for Paga")

        # order.id is already a unique, non-guessable uuid hex, which is
        # exactly what Paga wants for referenceNumber -- no separate ID
        # generation needed.
        result = paga_service.create_payment_request(
            reference_number=order.id,
            amount_kobo=order.amount_kobo,
            payer_name=user.full_name,
            payer_email=user.email,
            callback_url=f"{settings.APP_BASE_URL}/orders/paga/webhook",
        )

        order.paga_reference = result.reference_number
        self.orders.commit_and_refresh(order)

        return PagaInitResponse(
            reference=result.reference_number,
            web_payment_link=result.web_payment_link,
            bank_transfer_account_number=result.bank_transfer_account_number,
            ussd_short_code=result.ussd_short_code,
            expiry_datetime_utc=result.expiry_datetime_utc,
        )

    def paga_verify(self, order_id: str, user: models.User) -> OrderOut:
        """Manual "check now" fallback for a Paga order. Paga's own
        guidance is that the webhook (paga_webhook below) is the
        authoritative signal -- this exists for a person who wants to
        confirm status without waiting, using the documented but
        less-precise /status endpoint (see paga_service.is_status_fully_paid)."""
        order = self.orders.get_by_id(order_id)
        if not order or order.user_id != user.id:
            raise HTTPException(status_code=404, detail="Order not found")
        if not order.paga_reference:
            raise HTTPException(status_code=400, detail="No Paga transaction to verify")

        if order.status == models.OrderStatus.pending:
            status_data = paga_service.get_payment_status(order.paga_reference)
            if paga_service.is_status_fully_paid(status_data):
                self._assign_stock_and_credit(order)
                order = self.orders.commit_and_refresh(order)

        return self._to_out(order)

    def paga_webhook(self, payload: dict) -> None:
        """Handles Paga's Payment Request callback notification. This is
        the authoritative source of truth for a Paga order's fulfillment --
        see the module docstring in paga_service.py for why polling
        /status is a fallback, not the primary path.

        Reference: https://developer-docs.paga.com/docs/operations-1#14-payment-request-callback-notifications
        """
        if not paga_service.verify_webhook_hash(payload):
            raise HTTPException(status_code=401, detail="Invalid webhook hash")

        reference = payload.get("externalReferenceNumber")
        order = self.orders.get_by_id(reference) if reference else None
        if not order:
            # Don't 404 on an unknown reference -- Paga retries failed
            # webhooks up to 3 times, and a 4xx/5xx just triggers more
            # retries for a reference we'll never recognize.
            return

        if order.status != models.OrderStatus.pending:
            return  # already processed, e.g. a retried notification

        if payload.get("event") == "PAYMENT_COMPLETE" and payload.get("state") == "CONSUMED":
            self._assign_stock_and_credit(order)
            self.orders.commit_and_refresh(order)

    def my_orders(self, user_id: str) -> list[OrderOut]:
        return [self._to_out(o) for o in self.orders.list_for_user(user_id)]

    def list_all(self, status: Optional[models.OrderStatus]) -> list[OrderOut]:
        return [self._to_out(o) for o in self.orders.list_all(status)]

    def delete_order(self, order_id: str, user: models.User) -> None:
        """Let a user remove one of their own orders they've changed their
        mind about. Only orders that haven't been fulfilled can go -- a
        successful order has stock assigned to the buyer and its amount
        credited to their spend total, so erasing the row would leave both
        dangling. Pending/failed orders never got that far, so they're safe
        to drop entirely."""
        order = self.orders.get_by_id(order_id)
        if not order or order.user_id != user.id:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.status == models.OrderStatus.success:
            raise HTTPException(status_code=400, detail="A completed order can't be deleted")

        self.orders.delete(order)

    def approve_manual_order(self, order_id: str) -> OrderOut:
        """Admin approves a manual bank transfer after checking the
        uploaded proof of payment. Paga orders confirm themselves via the
        webhook (or paga_verify) instead -- this path is manual-only."""
        order = self.orders.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.payment_method != models.PaymentMethod.manual:
            raise HTTPException(status_code=400, detail="Only manual transfer orders need approval")
        if order.status != models.OrderStatus.pending:
            raise HTTPException(status_code=400, detail="This order has already been processed")
        if order.proof is None:
            raise HTTPException(
                status_code=400,
                detail="This order has no uploaded proof of payment to review",
            )

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