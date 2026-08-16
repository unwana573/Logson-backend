from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class FeedbackOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    message: str
    created_at: datetime

    class Config:
        from_attributes = True