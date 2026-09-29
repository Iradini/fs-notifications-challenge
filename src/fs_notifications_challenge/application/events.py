from dataclasses import dataclass

from fs_notifications_challenge.domain.notification import Notification


@dataclass(frozen=True)
class NotificationCreatedEvent:
    """Raised after a notification has been persisted.
    Carries the saved entity (so it already has its id) so listener
    without another DB round-trip for the basics.
    """

    notification: Notification