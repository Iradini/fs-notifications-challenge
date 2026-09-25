from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SendNotificationRequest(BaseModel):
    sender_id: int
    recipient_id: int
    title: str
    message: str = Field(min_length=1, max_length=500)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: int
    recipient_id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime