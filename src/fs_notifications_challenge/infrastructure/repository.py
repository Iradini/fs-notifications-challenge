# from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.notification import Channel, Notification, Status
from fs_notifications_challenge.infrastructure.models import NotificationModel


class SQLAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, notification: Notification) -> Notification:
        row = NotificationModel(
            id=notification.id,
            user_id=notification.user_id,
            title=notification.title,
            content=notification.content,
            channel=notification.channel.value,
            recipient=notification.recipient,
            status=notification.status,
            created_at=notification.created_at,
            sent_at=notification.sent_at,
            last_error=notification.last_error,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: NotificationModel) -> Notification:
        return Notification(
            id=row.id,
            user_id=row.user_id,
            title=row.title,
            content=row.content,
            channel=Channel(row.channel),
            recipient=row.recipient,
            status=Status(row.status),
            created_at=row.created_at,
            sent_at=row.sent_at,
            last_error=row.last_error,
        )
