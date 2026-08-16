from typing import Optional

from sqlalchemy.orm import Session

from app import models


class FeedbackRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, user_id: Optional[str], message: str) -> models.Feedback:
        feedback = models.Feedback(user_id=user_id, message=message)
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        return feedback

    def list_all(self) -> list[models.Feedback]:
        return self.db.query(models.Feedback).order_by(models.Feedback.created_at.desc()).all()