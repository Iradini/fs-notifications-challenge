import asyncio
import os
import sys
from collections.abc import AsyncGenerator

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ["DATABASE_URL"] = ("postgresql+psycopg://notificationuser:notificationpassword@localhost/test_notification")
os.environ.setdefault("SECRET_KEY", "test-secret-for-pytest-only-0123456789")


import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from fs_notifications_challenge.infrastructure.channels import build_channel_registry
from fs_notifications_challenge.infrastructure.database import Base
from fs_notifications_challenge.infrastructure.worker import _process_one_cycle
from fs_notifications_challenge.main import app

PASSWORD = "Test1234+"

@pytest.fixture(scope="session")
def test_engine():
    return create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)



@pytest.fixture(scope="session")
async def setup_database(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.fixture
async def clean_database(test_engine, setup_database) -> AsyncGenerator[None]:
    """Every test starts on empty tables. The app commits for real (its own get_db),
    so the worker and the tests' own sessions see exactly what the API wrote."""
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with test_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def client(clean_database) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def login(client, email="owner@example.com") -> None:
    """From now on `client` acts as this user (it sends their Bearer token)."""
    response = await client.post("/api/auth/token", data={"username": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


async def make_user(client, email="owner@example.com") -> int:
    """Register a user and log in as them."""
    response = await client.post("/api/users", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    await login(client, email)
    return response.json()["id"]


def body(**overrides):
    # No user_id: the owner is whoever the token belongs to
    return {
        "title": "Test", "content": "Test Content",
        "channel": "EMAIL", "recipient": {"email": "test@example.com"}, **overrides,
    }


async def run_worker_once():
    await _process_one_cycle(build_channel_registry(), poll_limit=10)
