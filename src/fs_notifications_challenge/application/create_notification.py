from dataclasses import dataclass

from fs_notifications_challenge.application.events import NotificationCreatedEvent
from fs_notifications_challenge.application.ports import (
    EventPublisher,
    NotificationRepository,
    UserRepository,
)
from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import NotFoundError
from fs_notifications_challenge.domain.notification import Notification


@dataclass
class CreateNotification:
    repository: NotificationRepository
    publisher: EventPublisher
    users: UserRepository

    async def execute(
            self,
            user_id: int,
            title: str,
            content: str,
            channel: Channel,
            recipient: ContactInfo,
    ) -> Notification:
        if await self.users.get(user_id) is None:
            raise NotFoundError(f"User {user_id} not found.")
        
        notification = Notification(
            user_id=user_id,
            title=title,
            content=content,
            channel=channel,
            recipient=recipient,
        )
        # Persist (flush) and enqueue in the same transaction; get_db commits.
        saved = await self.repository.add(notification)
        await self.publisher.publish(NotificationCreatedEvent(notification=saved))
        return saved