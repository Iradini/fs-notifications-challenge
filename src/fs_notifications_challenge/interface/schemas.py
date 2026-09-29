from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from fs_notifications_challenge.domain.notification import Channel, Status


class UserBase(BaseModel):
    email: EmailStr = Field(max_length=200)


class UserCreateRequest(UserBase):
    pass


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class NotificationBase(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=500)
    channel: Channel
    recipient: str


class NotificationCreateRequest(NotificationBase):
    user_id: int  # TEMPORARY 



class SendNotificationRequest(NotificationBase):
    sent_at: datetime | None = None


class NotificationResponse(NotificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: Status
    created_at: datetime
    sent_at: datetime | None = None
    last_error: str | None = None