from dataclasses import dataclass

from fs_notifications_challenge.application.outbox import OutboxRepository
from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain. errors import NotFoundError


@dataclass
class DeleteNotification:
    """Soft delete, any status. The notification, its delivery attempts and its
    outbox row all stay in the database for audit trail; the notification
    just dissapears from the API and a pending delivery is cancelled."""

    repository: NotificationRepository
    outbox: OutboxRepository

    
    async def execute(self, notification_id: int) -> None:
        notification = await self.repository.get(notification_id)  
        if notification is None:
            raise NotFoundError(f"Notification {notification_id} not found.")
        notification.delete()
        # A plain update, so it gets the same version check as PATCH: if the 
        # worker changed the row since we read it, this is a 409, not a silent overwrite
        await self.repository.update(notification)
        await self.outbox.cancel(notification.id)  # same transaction 