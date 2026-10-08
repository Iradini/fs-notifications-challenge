from __future__ import annotations 

from datetime import datetime
from typing import Annotated, Literal

import phonenumbers
from pydantic import (
    AfterValidator, 
    BaseModel, 
    ConfigDict, 
    EmailStr, 
    Field,  
    StringConstraints,
    model_serializer,
    model_validator,
)
from pydantic_core import PydanticCustomError
from pydantic_extra_types.phone_numbers import PhoneNumberValidator 

from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.notification import Notification, Status
from fs_notifications_challenge.domain.user import User

TOKEN_MIN_LENGTH = 32


def _check_token_length(value: str) -> str:
    if len(value) < TOKEN_MIN_LENGTH:
        raise PydanticCustomError(
            "token_too_short",
            "Tokens should have at least {min_length} characters",
            {"min_length": TOKEN_MIN_LENGTH},
        )
    return value


E164Phone = Annotated[str | phonenumbers.PhoneNumber, 
                      PhoneNumberValidator(default_region="UY",number_format="E164")]
PushToken = Annotated[
    str, 
    StringConstraints(strip_whitespace=True, max_length=4096, pattern=r"^[A-Za-z0-9_\-:.]+$"),
    AfterValidator(_check_token_length)
]

class ContactInfoRequest(BaseModel):
    """A profile: any of email/phone/token (a person can have all three)."""

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


class ProfileInfo(ContactInfoRequest):
    pass


# A notification's recipient only needs the address for its channel, so each
# channel gets its own recipient schema. extra="forbid": sending a phone on an
# EMAIL notification is a client mistake worth a 422, not something to drop silently

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailRecipient(_Strict):
    email: EmailStr

    def to_domain(self) -> ContactInfo:
        return ContactInfo(email=self.email)


class SMSRecipient(_Strict):
    phone: E164Phone

    def to_domain(self) -> ContactInfo:
        return ContactInfo(phone=self.phone)


class PushRecipient(_Strict):
    token: PushToken

    def to_domain(self) -> ContactInfo:
        return ContactInfo(token=self.token)


class RecipientPatch(_Strict):
    """PATCH can change the recipient without resending the channel, so it
    takes exactly one address; the domain checks it matches the channel."""

    email: EmailStr | None = None
    phone: E164Phone | None = None
    token: PushToken | None = None

    @model_validator(mode="after")
    def exactly_one(self):
        if sum(v is not None for v in (self.email, self.phone, self.token)) != 1:
            raise ValueError("Send exactly one of email, phone or token: the address for the notification's channel.")
        return self


    def to_domain(self) -> ContactInfo:
        return ContactInfo(self.email, self.phone, self.token)    


class ContactInfoResponse(BaseModel):
    """Response don't re-validate formats; they just echo what's stored, minus the
    empty fields, so a recipient comes back exactly as it was sent."""

    model_config = ConfigDict(from_attributes=True)

    email: str | None = None
    phone: str | None = None
    token: str | None = None

    @model_serializer(mode="wrap")
    def _drop_empty(self, handler):
        return {key: value for key, value in handler(self).items() if value is not None}


# --- users -------------------------------------------------------------------------

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


# --- notifications -----------------------------------------------------------------

Title = Annotated[str, Field(min_length=1, max_length=50)]
Content = Annotated[str, Field(min_length=1, max_length=500)]


class NotificationBase(BaseModel):
    title: Title
    content: Content
    channel: Channel


class _NotificationCreateBase(BaseModel):
    user_id: int  # TEMPORARY 
    title: Title
    content: Content


class EmailNotificationCreate(_NotificationCreateBase):
    channel: Literal[Channel.EMAIL]
    recipient: EmailRecipient


class SmsNotificationCreate(_NotificationCreateBase):
    channel: Literal[Channel.SMS]
    recipient: SMSRecipient


class PushNotificationCreate(_NotificationCreateBase):
    channel: Literal[Channel.PUSH]
    recipient: PushRecipient


# `channel` picks the schema (a discriminated union), so the docs and the
# validations both asks only for the address that channel uses. The route passes
# discriminator="channel" through Body(): FastAPI drops a Field() discriminator
# when the type is also wrapped in the Body()
NotificationCreateRequest = EmailNotificationCreate | SmsNotificationCreate | PushNotificationCreate
CHANNEL_DISCRIMINATOR = "channel"


class NotificationUpdateRequest(BaseModel):
    """PATCH: send only what changes. `recipient` replaces the whole recipient.
    title/content: any status. channel/recipient: only while CREATED (else 409)."""

    title: Title | None = None
    content: Content | None = None
    channel: Channel | None = None
    recipient: RecipientPatch | None = None

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