# from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.notification import Notification
from fs_notifications_challenge.infrastructure.models import NotificationModel


class SQLAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, notification: Notification) -> Notification:
        row = NotificationModel(
            sender_id=notification.sender_id,
            recipient_id=notification.recipient_id,
            title=notification.title,
            message=notification.message,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: NotificationModel) -> Notification:
        return Notification(
            id=row.id,
            sender_id=row.sender_id,
            recipient_id=row.recipient_id,
            title=row.title,
            message=row.message,
            is_read=row.is_read,
            created_at=row.created_at,
        )
