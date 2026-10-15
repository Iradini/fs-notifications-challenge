from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.change_password import ChangePassword
from fs_notifications_challenge.application.create_notification import CreateNotification
from fs_notifications_challenge.application.create_user import CreateUser
from fs_notifications_challenge.application.delete_notification import DeleteNotification
from fs_notifications_challenge.application.delete_user import DeleteUser
from fs_notifications_challenge.application.delete_user_profile import DeleteUserProfile
from fs_notifications_challenge.application.get_notification import GetNotification
from fs_notifications_challenge.application.get_user import GetUser
from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.application.log_in import LogIn
from fs_notifications_challenge.application.ports import PasswordHasher, TokenService
from fs_notifications_challenge.application.update_notification import UpdateNotification
from fs_notifications_challenge.application.update_user import UpdateUser
from fs_notifications_challenge.config import settings
from fs_notifications_challenge.infrastructure.database import get_db
from fs_notifications_challenge.infrastructure.outbox import (
    OutboxEventPublisher,
    SQLAlchemyOutboxRepository,
)
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository
from fs_notifications_challenge.infrastructure.security import Argon2PasswordHasher, JwtTokenService
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
    return CreateUser(repository=SQLAlchemyUserRepository(db), hasher=get_password_hasher())


def get_get_user(db: Db) -> GetUser:
    return GetUser(repository=SQLAlchemyUserRepository(db))


def get_delete_user_profile(db: Db) -> DeleteUserProfile:
    return DeleteUserProfile(repository=SQLAlchemyUserRepository(db))


def get_update_user(db: Db) -> UpdateUser:
    return UpdateUser(repository=SQLAlchemyUserRepository(db))


def get_change_password(db: Db) -> ChangePassword:
    return ChangePassword(repository=SQLAlchemyUserRepository(db), hasher=get_password_hasher())


def get_delete_user(db: Db) -> DeleteUser:
    return DeleteUser(repository=SQLAlchemyUserRepository(db), hasher=get_password_hasher())


# --- Auth -------------------------------------------------------------------

@lru_cache
def get_password_hasher() -> PasswordHasher:
    return Argon2PasswordHasher()


@lru_cache
def get_token_service() -> TokenService:
    return JwtTokenService(
        secret=settings.secret_key.get_secret_value(),
        algorith=settings.algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )


def get_login_in(db: Db) -> LogIn:
    return LogIn(users=SQLAlchemyUserRepository(db), hasher=get_password_hasher(), tokens=get_token_service())