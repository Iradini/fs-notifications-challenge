from dataclasses import dataclass

from fs_notifications_challenge.application.events import NotificationCreatedEvent
from fs_notifications_challenge.application.ports import (
    EventPublisher,
    NotificationRepository,
)
from fs_notifications_challenge.domain.notification import Channel, Notification


@dataclass
class CreateNotification:
    repository: NotificationRepository
    publisher: EventPublisher

    async def execute(
            self,
            user_id: int,
            title: str,
            content: str,
            channel: Channel,
            recipient: str,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            content=content,
            channel=channel,
            recipient=recipient,
        )
        # Persist and commit FIRST...
        saved = await self.repository.add(notification)
        # ... THEN publish, so any listener sees a commited row
        await self.publisher.publish(NotificationCreatedEvent(notification=saved))
        return saved