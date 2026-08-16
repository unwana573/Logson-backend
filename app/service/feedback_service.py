from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config.settings import get_settings
from app.repository.feedback_repository import FeedbackRepository
from app.schema.feedback import FeedbackCreate, FeedbackOut
from app.service.email_service import send_email

settings = get_settings()


class FeedbackService:
    def __init__(self, db: Session):
        self.db = db
        self.feedback = FeedbackRepository(db)

    @staticmethod
    def _to_out(f: models.Feedback) -> FeedbackOut:
        return FeedbackOut(
            id=f.id,
            user_id=f.user_id,
            user_email=f.user.email if f.user else None,
            message=f.message,
            created_at=f.created_at,
        )

    def submit(self, payload: FeedbackCreate, submitter: Optional[models.User]) -> FeedbackOut:
        feedback = self.feedback.create(
            user_id=submitter.id if submitter else None,
            message=payload.message,
        )

        # Best-effort notification -- if SendGrid isn't configured or the
        # send fails, the feedback is still saved (see send_email's own
        # False-not-raise behavior), so submission never fails just
        # because email delivery did.
        who = submitter.email if submitter else "an anonymous visitor"
        send_email(
            to_email=settings.FEEDBACK_NOTIFY_EMAIL,
            subject="New feedback on Logson",
            content=f"From: {who}\n\n{payload.message}",
        )

        return self._to_out(feedback)

    def list_all(self) -> list[FeedbackOut]:
        return [self._to_out(f) for f in self.feedback.list_all()]