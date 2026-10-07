from dataclasses import dataclass

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.errors import NotFoundError
from fs_notifications_challenge.domain.notification import Notification


@dataclass
class GetNotification:
    repository: NotificationRepository


    async def execute(self, notification_id: int) -> Notification:
        notification = await self.repository.get(notification_id)
        if notification is None:
            raise NotFoundError(f"Notification {notification_id} not found.")
        return notification