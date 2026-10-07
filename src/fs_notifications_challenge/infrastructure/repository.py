# from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from fs_notifications_challenge.application.ports import NotificationRepository
from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import ConcurrentUpdateError, NotFoundError
from fs_notifications_challenge.domain.notification import Notification, Status
from fs_notifications_challenge.infrastructure.models import NotificationModel


class SQLAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        # Rows this repository handed out as domain objects. The session only
        # holds rows weakly: without this, update() would re-SELECT a fresh row
        # (with the NEW version) and the optimistic-lock check would always pass,
        # silently overwriting a concurrent PATCH with stale data.
        self._loaded: dict[int, NotificationModel] = {}

    async def add(self, notification: Notification) -> Notification:
        row = NotificationModel(
            user_id=notification.user_id,
            title=notification.title,
            content=notification.content,
            channel=notification.channel.value,
            recipient_email=notification.recipient.email,
            recipient_phone=notification.recipient.phone,
            recipient_token=notification.recipient.token,
            status=notification.status.value,
            created_at=notification.created_at,
            sent_at=notification.sent_at,
            last_error=notification.last_error,
        )
        self._session.add(row)
        await self._session.flush()  # assigns id, commit happens in get_db 
        self._loaded[row.id] = row
        return self._to_domain(row)


    async def get(self, notification_id: int) -> Notification | None:
        row = await self._session.get(NotificationModel, notification_id)
        if row is None or row.deleted_at is not None:
            return None
        self._loaded[row.id] = row
        return self._to_domain(row)


    async def update(self, notification: Notification) -> Notification:
        row = self._loaded.get(notification.id) or await self._session.get(NotificationModel, notification.id)
        if row is None:
            raise ValueError(f"Notification {notification.id} not found")
        row.title = notification.title
        row.content = notification.content
        row.channel = notification.channel.value
        row.recipient_email = notification.recipient.email
        row.recipient_phone = notification.recipient.phone
        row.recipient_token = notification.recipient.token
        row.status = notification.status.value
        row.sent_at = notification.sent_at
        row.last_error = notification.last_error
        row.deleted_at = notification.deleted_at
        row.updated_at = notification.updated_at
        try:
            await self._session.flush()
        except StaleDataError as exc:
            raise ConcurrentUpdateError(
                f"Notification {notification.id} was changed by someone else; reload and retry.",
            ) from exc
        return self._to_domain(row)

    
    async def list_all(self) -> list[Notification]:
        result = await self._session.execute(
            select(NotificationModel)
            .where(NotificationModel.deleted_at.is_(None))
            .order_by(NotificationModel.created_at.desc()),
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
            recipient=ContactInfo(
                email=row.recipient_email,
                phone=row.recipient_phone,
                token=row.recipient_token,
            ),
            status=Status(row.status),
            created_at=row.created_at,
            sent_at=row.sent_at,
            last_error=row.last_error,
            deleted_at=row.deleted_at,
            updated_at=row.updated_at,
        )