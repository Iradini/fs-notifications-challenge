from typing import Annotated

from fastapi import Depends 
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.create_notification import CreateNotification
from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.application.listeners import log_notification_created
from fs_notifications_challenge.application.send_notification import SendNotification
from fs_notifications_challenge.infrastructure.database import get_db
from fs_notifications_challenge.infrastructure.events import InProcessEventPublisher
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository

# Provider receives a fresh pre-request AsyncSession via Depends(get_db)
# and builds the repository from it. No module-level session 
event_publisher = InProcessEventPublisher()
event_publisher.subscribe(log_notification_created)

def get_create_notification(
        db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateNotification:
    return CreateNotification(
        repository=SQLAlchemyNotificationRepository(db),
        publisher=event_publisher,
) 


def get_list_notifications(
        db: Annotated[AsyncSession, Depends(get_db)],
) -> ListNotifications:
    return ListNotifications(repository=SQLAlchemyNotificationRepository(db))


def get_send_notification(
        db: Annotated[AsyncSession, Depends(get_db)],
) -> SendNotification:
    return SendNotification(repository=SQLAlchemyNotificationRepository(db)) 