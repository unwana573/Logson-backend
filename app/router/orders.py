from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.deps import get_current_admin, get_current_user
from app.schema.order import OrderCreate, OrderOut, PaystackInitResponse
from app.service.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return OrderService(db).create_order(current_user, payload)


@router.post("/{order_id}/paystack/init", response_model=PaystackInitResponse)
def paystack_init(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return OrderService(db).paystack_init(order_id, current_user)


@router.post("/{order_id}/paystack/verify", response_model=OrderOut)
def paystack_verify(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return OrderService(db).paystack_verify(order_id, current_user)


@router.get("/me", response_model=list[OrderOut])
def my_orders(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return OrderService(db).my_orders(current_user.id)


@router.get("", response_model=list[OrderOut])
def list_all_orders(
    status: Optional[models.OrderStatus] = None,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    """Admin > Payments tab: view pending/successful orders across every
    user, for both manual transfer and Paystack."""
    return OrderService(db).list_all(status)


@router.post("/{order_id}/approve", response_model=OrderOut)
def approve_manual_order(
    order_id: str,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return OrderService(db).approve_manual_order(order_id)


@router.post("/{order_id}/reject", response_model=OrderOut)
def reject_order(
    order_id: str,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return OrderService(db).reject_order(order_id)
