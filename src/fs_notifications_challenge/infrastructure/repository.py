# from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.notification import Channel, Notification, Status
from fs_notifications_challenge.infrastructure.models import NotificationModel


class SQLAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> Notification:
        row = NotificationModel(
            id=notification.id,
            user_id=notification.user_id,
            title=notification.title,
            content=notification.content,
            channel=notification.channel.value,
            recipient=notification.recipient,
            status=notification.status.value,
            created_at=notification.created_at,
            sent_at=notification.sent_at,
            last_error=notification.last_error,
        )
        self._session.add(row)
        await self._session.flush()  # assigns id, commit happens in get_db 
        return self._to_domain(row)


    async def get(self, notification_id: int) -> Notification | None:
        row = await self._session.get(NotificationModel, notification_id)
        return self._to_domain(row) if row is not None else None


    async def update(self, notification: Notification) -> Notification:
        row = await self._session.get(NotificationModel, notification.id)
        if row is None:
            raise ValueError(f"Notification {notification.id} not found")
        row.status = notification.status.value
        row.sent_at = notification.sent_at
        row.last_error = notification.last_error
        await self._session.flush()
        return self._to_domain(row)

    
    async def list_all(self) -> list[Notification]:
        result = await self._session.execute(
            select(NotificationModel).order_by(NotificationModel.created_at.desc()),
        )
        return [self._to_domain(row) for row in result.scalars().all()]
    

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