from __future__ import annotations 

from datetime import datetime
from typing import Annotated

import phonenumbers
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator, StringConstraints
from pydantic_extra_types.phone_numbers import PhoneNumberValidator 

from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.notification import Notification, Status
from fs_notifications_challenge.domain.user import User


E164Phone = Annotated[str | phonenumbers.PhoneNumber, 
                      PhoneNumberValidator(default_region="UY",number_format="E164")]
PushToken = Annotated[
    str, 
    StringConstraints(strip_whitespace=True, min_length=32, max_length=4096, pattern=r"^[A-Za-z0-9_\-:.]+$")
]

class ContactInfoRequest(BaseModel):
    """Format checks for anything that carries email/phone/token. Recipient and
    profile both inherit this FIELD SET"""

    email: EmailStr | None = None
    phone: E164Phone | None = None
    token: PushToken | None = None

    @model_validator(mode="after")
    def at_least_one(self):
        if not (self.email or self.phone or self.token):
            raise ValueError("Provide at least one of email, phone or token.")
        return self

    
    def to_domain(self) -> ContactInfo:
        return ContactInfo(email=self.email, phone=self.phone, token=self.token)


class RecipientInfo(ContactInfoRequest):
    pass


class ProfileInfo(ContactInfoRequest):
    pass


class ContactInfoResponse(BaseModel):
    """Response don't re-validate formats; they just echo what's stored."""

    model_config = ConfigDict(from_attributes=True)

    email: str | None = None
    phone: str | None = None
    token: str | None = None


class UserCreateRequest(BaseModel):
    email: EmailStr 


class UserResponse(BaseModel):
    id: int
    email: str
    profile: ContactInfoResponse | None = None

    @classmethod
    def from_domain(cls, user: User) -> UserResponse:
        profile = ContactInfoResponse.model_validate(user.profile.contact) if user.profile else None
        return cls(id=user.id, email=user.email, profile=profile)


Title = Annotated[str, Field(min_length=1, max_length=50)]
Content = Annotated[str, Field(min_length=1, max_length=500)]

class NotificationBase(BaseModel):
    title: Title
    content: Content
    channel: Channel


class NotificationCreateRequest(NotificationBase):
    user_id: int  # TEMPORARY 
    recipient: RecipientInfo


class NotificationUpdateRequest(BaseModel):
    """PATCH: send only what changes. `recipient` replaces the whole recipient.
    title/content: any status. channel/recipient: only while CREATED (else 409)."""

    title: Title | None = None
    content: Content | None = None
    channel: Channel | None = None
    recipient: RecipientInfo | None = None

    @model_validator(mode="after")
    def something_to_change(self):
        if self.model_fields_set == set():
            raise ValueError("Send at least one of title, content, channel or recipient.")
        return self


class NotificationResponse(NotificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    recipient: ContactInfoResponse
    status: Status
    created_at: datetime
    sent_at: datetime | None = None
    updated_at: datetime | None = None
    last_error: str | None = None

    @classmethod
    def from_domain(cls, notification: Notification) -> NotificationResponse:
        return cls.model_validate(notification)