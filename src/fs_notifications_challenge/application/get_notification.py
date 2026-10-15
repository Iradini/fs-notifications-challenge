from dataclasses import dataclass

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.errors import NotFoundError
from fs_notifications_challenge.domain.notification import Notification


@dataclass
class GetNotification:
    repository: NotificationRepository


    async def execute(self, notification_id: int, user_id: int) -> Notification:
        notification = await self.repository.get(notification_id)
        if notification is None or notification.user_id != user_id:
            raise NotFoundError(f"Notification {notification_id} not found.")
        return notification