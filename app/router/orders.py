from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app import models
from app.config.database import get_db
from app.config.deps import get_current_admin, get_current_user
from app.schema.order import OrderCreate, OrderOut, PagaInitResponse
from app.service.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])

# Proof-of-payment uploads: cap the size and identify the real image type from
# the file's magic bytes instead of trusting the client's Content-Type header
# (which is trivially spoofed). We store the sniffed type.
MAX_PROOF_BYTES = 5 * 1024 * 1024  # 5 MB


def _sniff_image_type(data: bytes) -> Optional[str]:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return OrderService(db).create_order(current_user, payload)


@router.post("/{order_id}/proof", response_model=OrderOut)
async def upload_proof(
    order_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Owner uploads a proof-of-payment image (JPEG/PNG/WEBP, <=5 MB) for a
    pending manual-transfer order. Re-uploading replaces the previous image."""
    contents = await file.read()
    if len(contents) > MAX_PROOF_BYTES:
        raise HTTPException(status_code=413, detail="Proof image must be 5 MB or smaller")
    content_type = _sniff_image_type(contents)
    if content_type is None:
        raise HTTPException(status_code=400, detail="Proof must be a JPEG, PNG, or WEBP image")
    return OrderService(db).save_proof(
        order_id, current_user, image=contents, content_type=content_type
    )


@router.get("/{order_id}/proof")
def get_proof(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Streams the stored proof image back to the order's owner or any admin
    (used by the admin Payments view); 404 otherwise or if none was uploaded."""
    proof = OrderService(db).get_proof(order_id, current_user)
    return Response(content=proof.image, media_type=proof.content_type)


@router.post("/{order_id}/paga/init", response_model=PagaInitResponse)
def paga_init(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return OrderService(db).paga_init(order_id, current_user)


@router.post("/{order_id}/paga/verify", response_model=OrderOut)
def paga_verify(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Manual fallback check -- the webhook below is the primary path."""
    return OrderService(db).paga_verify(order_id, current_user)


@router.post("/paga/webhook", status_code=200)
async def paga_webhook(request: Request, db: Session = Depends(get_db)):
    """Public endpoint Paga's servers call directly -- no auth dependency,
    since the caller is Paga, not a signed-in user. Authenticity is
    verified via the request body's own hash field instead (see
    OrderService.paga_webhook / paga_service.verify_webhook_hash)."""
    payload = await request.json()
    OrderService(db).paga_webhook(payload)
    # Paga expects exactly this shape to acknowledge receipt and stop retrying.
    return {"status": "SUCCESS"}


@router.get("/me", response_model=list[OrderOut])
def my_orders(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return OrderService(db).my_orders(current_user.id)


@router.delete("/{order_id}", status_code=204)
def delete_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Remove a pending/failed order the buyer no longer wants. A
    successful (fulfilled) order can't be deleted -- see
    OrderService.delete_order."""
    OrderService(db).delete_order(order_id, current_user)


@router.get("", response_model=list[OrderOut])
def list_all_orders(
    status: Optional[models.OrderStatus] = None,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    """Admin > Payments tab: view pending/successful orders across every
    user, for both manual transfer and Paga."""
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