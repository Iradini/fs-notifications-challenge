from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import ConflictError, DomainError


__all__ = ["Channel", "Contact_Info", "DomainError", "Notification", "NotificationLockedError", "Status"]


class Status(str, Enum):
    CREATED ="CREATED"
    SENT = "SENT"
    FAILED = "FAILED"


class NotificationLockedError(ConflictError):
    """The status of the notification is not CREATED"""


@dataclass
class Notification():
    user_id: int
    title: str
    content: str
    channel: Channel
    recipient: ContactInfo
    id: int | None = None
    status: Status = Status.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    sent_at: datetime | None = None
    last_error: str | None = None
    # Soft delete: hidden from the API, kept for the audit trail. Orthogonal to
    # `status`: deleting doesn't change what happened to the delivery.
    deleted_at: datetime | None = None
    # Last time title/content were edited (None = never). Let's the UI show "edited".
    updated_at: datetime | None = None

    def __post_init__(self) -> None :
        self._check_text(self.title, self.content)
        self._check_recipient(self.channel, self.recipient)


    # --- invariants ----------------------------------------------------------
    @staticmethod
    def _check_text(title: str, content: str) -> None:
        if not title.strip():
            raise DomainError("Notification title cannot be blank.")
        if not content.strip():
            raise DomainError("Notification message cannot be blank.")


    @staticmethod
    def _check_recipient(channel: Channel, recipient: ContactInfo) -> None:
        if recipient.address_for(channel) is None:
            raise DomainError(
                f"A {channel.value} notification needs a recipient address for the channel.",
            )


    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    
    def _require_not_deleted(self) -> None:
        if self.is_deleted:
            raise NotificationLockedError("Notification was deleted; it can't change.")


    def _require_created(self, what: str = "it") -> None:
        self._require_not_deleted()
        if self.status is not Status.CREATED:
            raise NotificationLockedError(
                f"Notification is {self.status.value}; {what} can only change while it's CREATED.",
            )


    # --- behavior: the entity knows its own state transitions ------------------
    def edit(self, *, title: str | None = None, content: str | None = None) -> None:
        """Display text: editable in ANY status (except deleted), because the 
        notifications panel render it from here. Copies already delivered by 
        email/sms/push don't change; each DeliveryAttempt keeps what was sent."""
        self._require_not_deleted()
        new_title = self.title if title is None else title
        new_content = self.content if content is None else content
        self._check_text(new_title, new_content)       # validate first...
        if (new_title, new_content)  == (self.title, self.content):
            return
        self.title, self.content = new_title, new_content # ... then assign
        self.updated_at = datetime.now(UTC)


    def change_delivery(
            self, *, channel: Channel | None = None, recipient: ContactInfo | None = None,
    ) -> None:
        """Where it goes: only while CREATED (the spec's rule). After that it was
        already delivered to the old address; a different address is a NEW notification."""
        self._require_created("channel and recipient")
        new_channel = channel or self.channel
        new_recipient = recipient or self.recipient
        self._check_recipient(new_channel, new_recipient)
        self.channel, self.recipient = new_channel, new_recipient
        self.last_error = None  # an error about oldest address no longer applies


    def delete(self):
        """Allowed in any status. Idempotent: deleting twice keeps the first time."""
        if self.deleted_at is None:
            self.deleted_at = datetime.now(UTC)    

    
    def mark_sent(self) -> None:
        self._require_created()
        self.status = Status.SENT
        self.sent_at = datetime.now(UTC)
        self.last_error = None


    def mark_failed(self, error: str) -> None:
        self._require_created()
        self.status = Status.FAILED
        self.last_error = error


    def record_error(self, error: str) -> None:
        """A failed attempt that will be retried: keep the status (still CREATED)
        the latesr error so the API shows why it hasn't gone out yet."""
        self._require_created()
        self.last_error = error