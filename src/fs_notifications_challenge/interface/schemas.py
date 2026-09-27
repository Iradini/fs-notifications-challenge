from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from fs_notifications_challenge.domain.notification import Channel, Status


class NotificationBase(BaseModel):
    id: int
    user_id: int
    title: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=500)
    channel: Channel
    recipient: str
    status: Status
    created_at: datetime | None = None
    last_error: str | None = None


class NotificationCreateRequest(NotificationBase):
    pass 


class SendNotificationRequest(NotificationBase):
    sent_at: datetime | None = None


class NotificationResponse(NotificationBase):
    model_config = ConfigDict(from_attributes=True)

