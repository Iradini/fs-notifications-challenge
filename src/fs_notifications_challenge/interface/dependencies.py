from typing import Annotated

from fastapi import Depends 
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.create_notification import CreateNotification
from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.infrastructure.database import get_db
from fs_notifications_challenge.infrastructure.outbox import (
    OutboxEventPublisher,
    SQLAlchemyOutboxRepository,
)
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository


def get_create_notification(
        db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateNotification:
    # Repository and outbox publisher share the SAME session, so the notification
    # and its outbox row commit together (get_db commits once at request end)
    repository = SQLAlchemyNotificationRepository(db)
    publisher = OutboxEventPublisher(SQLAlchemyOutboxRepository(db))
    return CreateNotification(repository=repository, publisher=publisher) 


def get_list_notifications(
        db: Annotated[AsyncSession, Depends(get_db)],
) -> ListNotifications:
    return ListNotifications(repository=SQLAlchemyNotificationRepository(db))