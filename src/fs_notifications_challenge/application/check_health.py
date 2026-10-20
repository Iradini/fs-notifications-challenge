import asyncio
from dataclasses import dataclass

from fs_notifications_challenge.application.ports import DatabaseHealthCheck, OutboxHealthCheck


@dataclass(frozen=True)
class HealthReport:
    """What the check found, one flag per dependency. Adding a check means a new
        field here and one more line in CheckHealth."""
    
    database: bool
    outbox: bool
    
    @property
    def healthy(self) -> bool:
        return self.database and self.outbox


@dataclass
class CheckHealth:

    database: DatabaseHealthCheck
    outbox: OutboxHealthCheck
    
    async def execute(self) -> HealthReport:
        database, outbox = await asyncio.gather(
            self.database.is_available(), self.outbox.is_draining()
        )
        return HealthReport(database=database, outbox=outbox)