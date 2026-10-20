import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from fs_notifications_challenge.application.ports import DatabaseHealthCheck, OutboxHealthCheck
from fs_notifications_challenge.infrastructure.models import OutboxMessageModel
from fs_notifications_challenge.infrastructure.outbox import PENDING

logger = logging.getLogger("notifications.health")


class SQLAlchemyDatabaseHealthCheck(DatabaseHealthCheck):
    """SELECT 1 on a connection of its own: no session and no transaction to commit,
    and a database that hangs can't keep the probe waiting longer than `timeout`."""


    def __init__(self, engine: AsyncEngine, timeout: float = 2.0) -> None:
        self._engine = engine
        self._timeout = timeout


    async def is_available(self) -> bool:
        try:
            async with asyncio.timeout(self._timeout):
                async with self._engine.connect() as connection:
                    await connection.execute(text('SELECT 1'))
        except Exception:   # noqa: BLE001 - whatever went wrong, the answer is "not available"
            logger.warning("Database health check failed", exc_info=True)
            return False
        return True


class SQLAlchemyOutboxHealthCheck(OutboxHealthCheck):
    """The outbox is draining unless a message has been DUE for longer than `max_lag`.

    The worker polls every couple of seconds and takes every PENDING message whose
    next_attempt_at has passed, so one that stays due for a minute means the worker is
    down, stuck, or failing every cycle. Messages waiting out a retry backoff are not
    due yet, and DONE/DEAD/CANCELLED ones are finished: neither counts."""

    def __init__(
            self, engine: AsyncEngine, max_lag: timedelta = timedelta(seconds=60), timeout: float = 2.0     
    ) -> None:
        self._engine = engine
        self._max_lag = max_lag
        self._timeout = timeout

    async def is_draining(self) -> bool:
        overdue = exists().where(
            OutboxMessageModel.status == PENDING,
            OutboxMessageModel.next_attempt_at <= datetime.now(UTC) -self._max_lag,
        )
        try:
            async with asyncio.timeout(self._timeout):
                async with self._engine.connect() as connection:
                    has_overdue = (await connection.execute(select(overdue))).scalar_one()
        except Exception:  # if we can't look, we can't vouch for it
            logger.warning("Outbox health check failed", exc_info=True)
            return False
        return not has_overdue 