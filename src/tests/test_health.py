"""GET /health: the use case, the SQLAlchemy adapter and the endpoint."""

import asyncio
import itertools
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from fs_notifications_challenge.application.check_health import CheckHealth, HealthReport
from fs_notifications_challenge.application.ports import DatabaseHealthCheck, OutboxHealthCheck
from fs_notifications_challenge.config import settings
from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal, engine
from fs_notifications_challenge.infrastructure.health import SQLAlchemyDatabaseHealthCheck, SQLAlchemyOutboxHealthCheck
from fs_notifications_challenge.infrastructure.models import NotificationModel, OutboxMessageModel, UserModel
from fs_notifications_challenge.infrastructure.outbox import CANCELLED, DEAD, DONE, PENDING
from fs_notifications_challenge.interface.dependencies import get_check_health
from fs_notifications_challenge.main import app
from tests.conftest import body, make_user, run_worker_once


class FakeDatabaseHealthCheck(DatabaseHealthCheck):
    def __init__(self, available: bool) -> None:
        self.available = available

    async def is_available(self) -> bool:
        return self.available


class FakeOutboxHealthCheck(OutboxHealthCheck):
    def __init__(self, draining: bool) -> None:
        self.draining = draining

    async def is_draining(self) -> bool:
        return self.draining


def _engine_on_port(port: int):
    """An engine for the test database's address, but on another port."""
    url = make_url(settings.database_url).set(port=port)
    return create_async_engine(url, poolclass=NullPool)


_emails = itertools.count(1)


async def _outbox_row(status: str = PENDING, due: timedelta = timedelta(0)) -> None:
    """One outbox message whose next_attempt_at was `due` ago (negative: still in the
    future, i.e. waiting out a retry backoff). Needs the clean_database fixture."""
    async with AsyncSessionLocal() as session:
        user = UserModel(email=f"user{next(_emails)}@example.com", password_hash="not-a-real-hash")
        session.add(user)
        await session.flush()
        notification = NotificationModel(
            user_id=user.id, title="Hi", content="There", channel="EMAIL", recipient_email="a@example.com",
        )
        session.add(notification)
        await session.flush()
        session.add(OutboxMessageModel(
            notification_id=notification.id, status=status, next_attempt_at=datetime.now(UTC) - due,
        ))
        await session.commit()


# --- application: the use case, with a fake -------------------------------------------

@pytest.mark.parametrize(("database", "outbox", "healthy"), [
    (True, True, True),
    (False, True, False),
    (True, False, False),
    (False, False, False),
])
async def test_healthy_only_when_every_check_passes(database, outbox, healthy):
    use_case = CheckHealth(FakeDatabaseHealthCheck(database), FakeOutboxHealthCheck(outbox))
    report = await use_case.execute()
    assert report == HealthReport(database=database, outbox=outbox)
    assert report.healthy is healthy


# --- infrastructure: the database adapter, against the real test database -------------

async def test_the_adapter_says_yes_when_the_database_answers(setup_database):
    assert await SQLAlchemyDatabaseHealthCheck(engine).is_available() is True


async def test_the_adapter_says_no_when_nothing_listens():
    dead = _engine_on_port(1)
    try:
        assert await SQLAlchemyDatabaseHealthCheck(dead).is_available() is False
    finally:
        await dead.dispose()


async def test_the_adapter_gives_up_on_a_database_that_never_answers():
    async def accept_and_stay_silent(reader, writer):
        await asyncio.sleep(30)

    server = await asyncio.start_server(accept_and_stay_silent, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    hung = _engine_on_port(port)
    try:
        started = time.monotonic()
        async with asyncio.timeout(3):             # a lost timeout fails here instead of hanging the suite
            assert await SQLAlchemyDatabaseHealthCheck(hung, timeout=0.3).is_available() is False
        assert time.monotonic() - started < 3      # it did not wait for the database
    finally:
        await hung.dispose()
        server.close()


# --- infrastructure: the outbox adapter ------------------------------------------------

@pytest.mark.usefixtures("clean_database")
class TestOutboxAdapter:
    """Draining = nothing has been DUE for longer than max_lag (60s unless a test says so)."""

    async def test_an_empty_outbox_is_draining(self):
        assert await SQLAlchemyOutboxHealthCheck(engine).is_draining() is True

    async def test_a_message_that_was_just_queued_is_draining(self):
        await _outbox_row(PENDING, due=timedelta(seconds=1))
        assert await SQLAlchemyOutboxHealthCheck(engine).is_draining() is True

    async def test_a_message_due_for_longer_than_the_allowed_lag_is_not_draining(self):
        await _outbox_row(PENDING, due=timedelta(minutes=5))
        assert await SQLAlchemyOutboxHealthCheck(engine).is_draining() is False

    async def test_the_allowed_lag_is_the_threshold(self):
        await _outbox_row(PENDING, due=timedelta(seconds=30))
        assert await SQLAlchemyOutboxHealthCheck(engine, max_lag=timedelta(seconds=60)).is_draining() is True
        assert await SQLAlchemyOutboxHealthCheck(engine, max_lag=timedelta(seconds=10)).is_draining() is False

    async def test_a_message_waiting_out_its_retry_backoff_is_fine(self):
        await _outbox_row(PENDING, due=-timedelta(minutes=5))      # next_attempt_at in the future
        assert await SQLAlchemyOutboxHealthCheck(engine).is_draining() is True

    @pytest.mark.parametrize("status", [DONE, DEAD, CANCELLED])
    async def test_finished_messages_never_count(self, status):
        await _outbox_row(status, due=timedelta(days=1))
        assert await SQLAlchemyOutboxHealthCheck(engine).is_draining() is True

    async def test_one_overdue_message_among_healthy_ones_is_enough(self):
        await _outbox_row(DONE, due=timedelta(days=1))
        await _outbox_row(PENDING, due=-timedelta(minutes=5))
        await _outbox_row(PENDING, due=timedelta(minutes=5))
        assert await SQLAlchemyOutboxHealthCheck(engine).is_draining() is False

    async def test_it_says_no_when_the_database_is_unreachable(self):
        dead = _engine_on_port(1)
        try:
            assert await SQLAlchemyOutboxHealthCheck(dead).is_draining() is False
        finally:
            await dead.dispose()


# --- interface: the endpoint -----------------------------------------------------------
# No overrides here except for the database-down case: these go through the real wiring.

async def test_health_is_public_and_healthy(client):
    response = await client.get("/health")                  # no login, on purpose
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "checks": {"database": "up", "outbox": "up"}}
    assert response.headers["cache-control"] == "no-store"


async def test_health_answers_head_requests_too(client):
    assert (await client.head("/health")).status_code == 200


async def test_health_follows_the_outbox_from_stuck_to_drained(client):
    await make_user(client)
    created = await client.post("/api/notifications", json=body())
    assert created.status_code == 201, created.text

    # Just created, worker hasn't run yet: waiting, but not for long
    assert (await client.get("/health")).status_code == 200

    # ...and nobody picks it up for ten minutes (the worker is down)
    async with AsyncSessionLocal() as session:
        message = (await session.execute(select(OutboxMessageModel))).scalar_one()
        message.next_attempt_at = datetime.now(UTC) - timedelta(minutes=10)
        await session.commit()

    stuck = await client.get("/health")
    assert stuck.status_code == 503
    assert stuck.headers["content-type"] == "application/json"
    assert stuck.json() == {"status": "unhealthy", "checks": {"database": "up", "outbox": "down"}}

    # The worker comes back and drains it
    await run_worker_once()

    recovered = await client.get("/health")
    assert recovered.status_code == 200
    assert recovered.json()["checks"] == {"database": "up", "outbox": "up"}


async def test_health_is_a_json_503_when_the_database_is_down(client):
    dead = _engine_on_port(1)
    app.dependency_overrides[get_check_health] = lambda: CheckHealth(
        database=SQLAlchemyDatabaseHealthCheck(dead),
        outbox=SQLAlchemyOutboxHealthCheck(dead),
    )
    try:
        response = await client.get("/health")
    finally:
        app.dependency_overrides.pop(get_check_health, None)
        await dead.dispose()

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/json"   # not the HTML error page
    # With the database gone the outbox can't be inspected either, so it is "down" too
    assert response.json() == {"status": "unhealthy", "checks": {"database": "down", "outbox": "down"}}
    assert response.headers["cache-control"] == "no-store"
