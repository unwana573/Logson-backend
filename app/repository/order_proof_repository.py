from typing import Optional

from sqlalchemy.orm import Session

from app import models


class OrderProofRepository:
    """Persists the proof-of-payment image bytes for an order. One row per
    order (order_id is unique), so uploading again replaces the stored image
    rather than adding a second row."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_order_id(self, order_id: str) -> Optional[models.OrderProof]:
        return (
            self.db.query(models.OrderProof)
            .filter(models.OrderProof.order_id == order_id)
            .first()
        )

    def upsert(self, *, order_id: str, image: bytes, content_type: str) -> models.OrderProof:
        proof = self.get_by_order_id(order_id)
        if proof:
            proof.image = image
            proof.content_type = content_type
        else:
            proof = models.OrderProof(order_id=order_id, image=image, content_type=content_type)
            self.db.add(proof)
        self.db.commit()
        self.db.refresh(proof)
        return proof
