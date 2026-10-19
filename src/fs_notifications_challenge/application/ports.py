from abc import ABC, abstractmethod

from fs_notifications_challenge.application.events import NotificationCreatedEvent
from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.delivery import DeliveryAttempt, DeliveryResult
from fs_notifications_challenge.domain.notification import Notification
from fs_notifications_challenge.domain.password_reset import PasswordResetToken
from fs_notifications_challenge.domain.user import User


class NotificationRepository(ABC):
    @abstractmethod
    async def add(self, notification: Notification) -> Notification:
        """Persist a notification (asigns its id). Does NOT commit; the 
        session lifecycle (get_db) commits once per request."""
        ...


    @abstractmethod
    async def get(self, notification_id: int) -> Notification | None:
        """Load one notification by id, or None if it doesn't exists OR was
        soft-deleted (deleted notifications are invisible to every use case)."""
        ...


    @abstractmethod
    async def update(self, notification: Notification) -> Notification:
        """Persist every mutable field. Raises ConcurrentUpdateError if someone
        else changed the row since it was loaded."""
        ...


    @abstractmethod
    async def list_for_user(self, user_id: int, *, skip: int, limit: int) -> list[Notification]:
        """One page of the user's non-deleted notifications, newest first. The id
        breaks created_at ties, so a page boundary never reshuffles rows."""
        ...


    @abstractmethod
    async def count_for_user(self, user_id: int) -> int:
        """How many non-deleted notifications the user has in total (every page)."""
        ...


class DeliveryAttemptRepository(ABC):
    @abstractmethod
    async def add(self, attempt: DeliveryAttempt) -> DeliveryAttempt:
        ...


class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> User:
        """Persist a new user (assing its id)."""
        ...


    @abstractmethod
    async def get(self, user_id: int) -> User | None:
        """Load a user by id or None"""
        ...


    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        ...
        

    @abstractmethod
    async def delete(self, user: User) -> None:
        """Erase the user and everything that belongs to them (profile, 
        notifications, their outbox rows and delivery attempts)."""
        ...


    @abstractmethod
    async def update(self, user: User) -> User:
        """Persist the user's new email and profile (creating, replacing or removing
        the profile row to match). Raises ConflictError if the email is taken."""
        ...


class EventPublisher(ABC):
    """Publishing an event. The outbox implementation records it as a durable 
    row in the same transaction as the notification, so a broker or a different 
    transport can replace it without touching the use cases."""
    
    @abstractmethod
    async def publish(self, event: NotificationCreatedEvent) -> None:
        ...


class ChannelSender(ABC):
    """Strategy for one delivery channel. Each implementation owns its
    channel-specific steps (validate, render/format, transmit) and reports the
    outcome as a DeliveryResult. Adding a channel = a new subclass registered
    in the ChannelRegistry; nothing else changes (open/closed)."""

    channel: Channel

    
    @abstractmethod
    async def send(self, notification: Notification) -> DeliveryResult:
        """Must not raise for expected failures. Return
        DeliveryResult.rejected(...) or DeliveryResult.transient(...)."""
        ...


class PasswordHasher(ABC):
    """Turns password into hashes and checks them. The algorithm is a detail."""


    @abstractmethod
    def hash_password(self, password: str) -> str:
        ...

    @abstractmethod
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        ...


class TokenService(ABC):
    """Issues and checks access token. Callers never sees JWT, claims or keys."""


    @abstractmethod
    def issue(self, user_id: int) -> str:
        ...


    @abstractmethod
    def verify_access_token(self, token: str) -> int:
        """Return the user id. Raise AuthenticationError if invalid or expired."""
        ...


class ResetTokenService(ABC):
    """The secrets inside password-reset links. How they are made and hashed is a
    security detail the use cases should not know (and tests can replace)."""


    @abstractmethod
    def generate(self) -> str:
        """A fresh, unguessable secret. This is what goes in the email."""
        ...


    @abstractmethod
    def digest(self, token: str) -> str:
        """What is stored and looked up. The same token always gives the same digest."""
        ...


class PasswordResetTokenRepository(ABC):
    @abstractmethod
    async def add(self, token: PasswordResetToken) -> PasswordResetToken:
        """Persist a token (assigns its id). Does NOT commit: get_db does, once per
        request."""
        ...

    @abstractmethod
    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        ...


    @abstractmethod
    async def delete_for_user(self, user_id: int) -> None:
        """Remove every reset token of this user (user, replaced or no longer wanted)."""
        ...


class PasswordResetMailer(ABC):
    """Tells a person how to reset their password. Whether that is SMTP, an API or 
    a log lines is the adapter's business; the use case only says WHO and WITH WHAT."""


    @abstractmethod
    async def send_reset_link(self, to_email: str, token: str) -> None:
        ...
