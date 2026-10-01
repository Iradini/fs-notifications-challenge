from dataclasses import dataclass

from fs_notifications_challenge.application.ports import (
    DeliveryAttemptRepository,
    NotificationRepository,
)
from fs_notifications_challenge.domain.delivery import AttemptStatus, DeliveryAttempt
from fs_notifications_challenge.domain.notification import DomainError


@dataclass
class DeliverNotification:
    """The 'listener' work, driven by the outbox worker. Loads a notification,
    attempts delivery, records the outcome on the notification and as a
    DeliveryAttempt.
    """

    notifications: NotificationRepository
    attempts: DeliveryAttemptRepository

    async def execute(self, notification_id: int) -> None:
        notification = await self.notifications.get(notification_id)
        if notification is None:
            raise DomainError(f"Notification {notification_id} not found.")

        notification.mark_sent()

        await self.notifications.update(notification)
        await self.attempts.add(
            DeliveryAttempt(
                notification_id=notification.id,
                channel=notification.channel,
                status=AttemptStatus.SUCCESS,
                detail={"simulated": True},
            ),
        )