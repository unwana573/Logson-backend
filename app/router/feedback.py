from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.config.database import get_db
from app.config.deps import get_current_admin, get_current_user
from app.schema.feedback import FeedbackCreate, FeedbackOut
from app.service.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=201)
def submit_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """A signed-in user's opinion/suggestion. Saved to the DB and emailed
    to FEEDBACK_NOTIFY_EMAIL immediately -- see FeedbackService.submit."""
    return FeedbackService(db).submit(payload, submitter=current_user)


@router.get("", response_model=list[FeedbackOut])
def list_feedback(db: Session = Depends(get_db), _admin: models.User = Depends(get_current_admin)):
    return FeedbackService(db).list_all()