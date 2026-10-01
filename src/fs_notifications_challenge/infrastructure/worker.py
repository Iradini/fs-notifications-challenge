import asyncio
import logging

from fs_notifications_challenge.application.deliver_notification import DeliverNotification
from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal
from fs_notifications_challenge.infrastructure.delivery_repository import SQLAlchemyDeliveryAttemptRepository
from fs_notifications_challenge.infrastructure.outbox import SQLAlchemyOutboxRepository
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository


logger = logging.getLogger("notifications.worker")


async def _process_one_cycle(poll_limit: int) -> None:
    # The worker runs outside any request, so it owns its own session and commit
    # itself (one commit per message, so each delivery is atomic on its own.)
    async with AsyncSessionLocal() as session:
        outbox = SQLAlchemyOutboxRepository(session)
        deliver = DeliverNotification(
            notifications=SQLAlchemyNotificationRepository(session),
            attempts=SQLAlchemyDeliveryAttemptRepository(session),
        )
        pending = await outbox.fetch_pending(limit=poll_limit)
        for message in pending:
            try:
                await deliver.execute(message.notification_id)
                await outbox.mark_done(message.id)
                await session.commit()
            except Exception as exc:  # noqa: BLE001 - worker must not die on one bad message
                await session.rollback()
                await outbox.mark_failed(message.id, str(exc))
                await session.commit()
                logger.exception("Delivery failed for outbox message %s", message.id)


async def run_outbox_worker(poll_interval: float = 2.0, poll_limit: int = 10) -> None:
    """Poll the outbox forever. Started as a background task in the app lifespan."""
    logger.info("Outbox worker started (every %.1fs).", poll_interval)
    while True:
        try:
            await _process_one_cycle(poll_limit)
        except asyncio.CancelledError:
            logger.info("Outbox worker stopping.")
            raise
        except Exception:  # noqa: BLE001 - keep the loop alive across unexpected errors
            logger.exception("Outbox worker crashed; continuing.")
        await asyncio.sleep(poll_interval)