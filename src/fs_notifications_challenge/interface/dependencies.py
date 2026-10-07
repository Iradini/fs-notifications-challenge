from typing import Annotated

from fastapi import Depends 
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.create_notification import CreateNotification
from fs_notifications_challenge.application.create_user import CreateUser
from fs_notifications_challenge.application.delete_notification import DeleteNotification
from fs_notifications_challenge.application.get_notification import GetNotification
from fs_notifications_challenge.application.get_user import GetUser
from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.application.save_user_profile import SaveUserProfile
from fs_notifications_challenge.application.update_notification import UpdateNotification
from fs_notifications_challenge.infrastructure.database import get_db
from fs_notifications_challenge.infrastructure.outbox import (
    OutboxEventPublisher,
    SQLAlchemyOutboxRepository,
)
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository
from fs_notifications_challenge.infrastructure.user_repository import SQLAlchemyUserRepository

Db = Annotated[AsyncSession, Depends(get_db)]


# --- notifications --------------------------------------------------------------

def get_create_notification(db: Db) -> CreateNotification:
    # Repository and outbox publisher share the SAME session, so the notification
    # and its outbox row commit together (get_db commits once at request end)
    return CreateNotification(
        repository=SQLAlchemyNotificationRepository(db), 
        publisher=OutboxEventPublisher(SQLAlchemyOutboxRepository(db)),
        users=SQLAlchemyUserRepository(db),
    ) 


def get_list_notifications(db: Db) -> ListNotifications:
    return ListNotifications(repository=SQLAlchemyNotificationRepository(db))


def get_get_notification(db: Db) -> GetNotification:
    return GetNotification(repository=SQLAlchemyNotificationRepository(db))


def get_update_notification(db: Db) -> UpdateNotification:
    return UpdateNotification(
        repository=SQLAlchemyNotificationRepository(db),
        outbox=SQLAlchemyOutboxRepository(db),    
    )


def get_delete_notification(db: Db) -> DeleteNotification:
    return DeleteNotification(
        repository=SQLAlchemyNotificationRepository(db),
        outbox=SQLAlchemyOutboxRepository(db),    
    )

# --- Users ------------------------------------------------------------------

def get_create_user(db: Db) -> CreateUser:
    return CreateUser(repository=SQLAlchemyUserRepository(db))


def get_get_user(db: Db) -> GetUser:
    return GetUser(repository=SQLAlchemyUserRepository(db))


def get_save_user_profile(db: Db) -> SaveUserProfile:
    return SaveUserProfile(repository=SQLAlchemyUserRepository(db))