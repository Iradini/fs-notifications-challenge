from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.ports import DeliveryAttemptRepository
from fs_notifications_challenge.domain.delivery import DeliveryAttempt
from fs_notifications_challenge.infrastructure.models import DeliveryAttemptModel


class SQLAlchemyDeliveryAttemptRepository(DeliveryAttemptRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def add(self, attempt: DeliveryAttempt) -> DeliveryAttempt:
        row = DeliveryAttemptModel(
            notification_id=attempt.notification_id,
            channel=attempt.channel.value,
            status=attempt.status.value,
            attempted_at=attempt.attempted_at,
            detail=attempt.detail,
        )
        self._session.add(row)
        await self._session.flush()
        attempt.id = row.id
        return attempt