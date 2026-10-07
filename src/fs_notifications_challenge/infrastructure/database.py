from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    async_sessionmaker, 
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from fs_notifications_challenge.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_async_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:
    # SQLite ignores foreign keys unless asked, per connection. Postgres always
    # enforces them, so turning this on keeps dev and prod behaving the same.
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_= AsyncSession, 
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """One transaction per request. Repositories add/flush but never commit;
    this commits once the request succeds, so a notification and its
    outbox row commit together (atomic outbox). Rolls back on any error.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session 
            await session.commit()
        except Exception:
            await session.rollback()
            raise