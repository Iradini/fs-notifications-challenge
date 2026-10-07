"""HTTP-level tests: real app, real repositories, throaway SQLite.
The background worker isn't started (no lifespan); test drive it explicitly."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fs_notifications_challenge.domain.errors import ConcurrentUpdateError
from fs_notifications_challenge.infrastructure.channels import build_channel_registry
from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal, Base, engine
from fs_notifications_challenge.application.deliver_notification import DeliverNotification
from fs_notifications_challenge.infrastructure.delivery_repository import SQLAlchemyDeliveryAttemptRepository
from fs_notifications_challenge.infrastructure.models import DeliveryAttemptModel, NotificationModel, OutboxMessageModel
from fs_notifications_challenge.infrastructure.outbox import SQLAlchemyOutboxRepository
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository
from fs_notifications_challenge.infrastructure.worker import _process_message, _process_one_cycle
from fs_notifications_challenge.main import app

TOKEN = "fcm_" + "a1B2c3D4" * 8


@pytest.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await engine.dispose()  # each test gets its own event loop ; don't reuse pooled connections


async def make_user(client, email="owner@example.com") -> int:
    response = await client.post("/api/notifications/users", json={"email": email})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def body(user_id, **overrides):
    return {
        "user_id": user_id, "title": "Test", "content": "Test Content",
        "channel": "EMAIL", "recipient": {"email": "test@example.com"}, **overrides,
    }


async def run_worker_once():
    await _process_one_cycle(build_channel_registry(), poll_limit=10)


# --- users & profiles ------------------------------------------------------------------

async def test_duplicate_user_email_is_409(client):
    await make_user(client)
    assert (await client.post("/api/notifications/users", json={"email": "owner@example.com"})).status_code == 409


async def test_profile_is_validated_and_normalized(client):
    uid = await make_user(client)
    ok = await client.put(f"/api/notifications/users/{uid}/profile", json={"phone": "+598 99 123 456", "token": TOKEN})
    assert ok.status_code == 200
    assert ok.json()["profile"] == {"email": None, "phone": "+59899123456", "token": TOKEN}
    assert (await client.put(f"/api/notifications/users/{uid}/profile", json={})).status_code == 422
    assert (await client.put("/api/notifications/users/999/profile", json={"email": "a@b.co"})).status_code == 404


# --- create -------------------------------------------------------------------------------------

@pytest.mark.parametrize(("overrides", "where"), [
    ({"recipient": {"email": "string"}}, ["body", "recipient", "email"]),
    ({"recipient": {"token": "string"}}, ["body", "recipient", "token"]),
    ({"recipient": {"phone": "string"}}, ["body", "recipient", "phone"]),
    ({"recipient": {}}, ["body", "recipient"]),
])
async def test_invalid_recipient_formats_are_422(client, overrides, where):
    uid = await make_user(client)
    response = await client.post("/api/notifications", json=body(uid, **overrides))
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == where


async def test_channel_without_matching_address_is_422(client):
    uid = await make_user(client)
    response = await client.post("/api/notifications", json=body(uid, channel="SMS"))
    assert response.status_code == 422
    assert "SMS" in response.json()["detail"]


async def test_unknow_user_is_404(client):
    assert (await client.post("/api/notifications", json=body(999))).status_code == 404


async def test_create_get_and_worker_sends_it(client):
    uid = await make_user(client)
    created = await client.post("/api/notifications", json=body(uid))
    assert created.status_code == 201
    nid = created.json()["id"]
    assert created.json()["status"] == "CREATED"
    assert created.json()["recipient"]["email"] == "test@example.com"

    await run_worker_once()
    fetched = await client.get(f"/api/notifications/{nid}")
    assert fetched.json()['status'] == "SENT" and fetched.json()["sent_at"]
    assert (await client.get("/api/notifications/999")).status_code == 404 


# --- update -----------------------------------------------------------------------

async def test_patch_redirects_while_created_and_resets_outbox(client):
    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]

    # simulate a delivery waiting out a long backoff
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(OutboxMessageModel))).scalar_one()
        row.attempts, row.last_error = 2, "smtp timeout"
        await s.commit()

    patched = await client.patch(
        f"/api/notifications/{nid}",
        json={"channel": "SMS", "recipient": {"phone": "+598 99 123 456"}},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["channel"] == "SMS"
    assert patched.json()["recipient"] == {"email": None, "phone": "+59899123456", "token": None}

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(OutboxMessageModel))).scalar_one()
        assert (row.status, row.attempts, row.last_error) == ("PENDING", 0, None)

    await run_worker_once()
    sent = (await client.get(f"/api/notifications/{nid}")).json()
    assert (sent["status"], sent["channel"]) == ("SENT", "SMS")


async def test_patch_rule(client):
    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]

    # Channel switch checked against the STORED recipient (only has an email)
    assert (await client.patch(f"/api/notifications/{nid}", json={"channel": "PUSH"})).status_code == 422
    assert (await client.patch(f"/api/notifications/{nid}", json={})).status_code == 422
    assert (await client.patch(f"/api/notifications/{nid}", json={"title": "New"})).json()["title"] == "New"
    assert (await client.patch("/api/notifications/999", json={"title": "x"})).status_code == 404

    await run_worker_once()
    # After SENT: text is still editable (the panel shows it)...
    edited = await client.patch(f"/api/notifications/{nid}", json={"content": "Corrected"})
    assert edited.status_code == 200
    assert (edited.json()["status"], edited.json()["content"]) == ("SENT", "Corrected")
    assert edited.json()["updated_at"] is not None 
    # ...but where it went is history: 409, and nothing in the request is applied
    locked   = await client.patch(
        f"/api/notifications/{nid}",
        json={"title": "Also new", "channel": "SMS", 'recipient': {"phone": "+59899123456"}},
    )
    assert locked.status_code == 409
    assert "CREATED" in locked.json()["detail"]
    assert (await client.get(f"/api/notifications/{nid}")).json()["title"] == "New"


async def test_editing_after_sent_keeps_what_was_delivered(client):
    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]
    await run_worker_once()
    await client.patch(f"/api/notifications/{nid}", json={"title": "Edited", "content": "New Text"})

    async with AsyncSessionLocal() as s:
        [attempt] = (await s.execute(select(DeliveryAttemptModel))).scalars().all()
    assert attempt.detail["message"] == {"title": "Test", "content": "Test Content"}  # the audit trail didn't move


# --- persistence guarantees --------------------------------------------------------------

async def test_worker_and_patch_race_is_detected(client):
    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]

    async with AsyncSessionLocal() as worker_s, AsyncSessionLocal() as api_s: 
        worker_repo = SQLAlchemyNotificationRepository(worker_s)
        api_repo = SQLAlchemyNotificationRepository(api_s)
        seen_by_worker = await worker_repo.get(nid)
        seen_by_api = await api_repo.get(nid)

        seen_by_api.edit(title="Changed")
        await api_repo.update(seen_by_api)
        await api_s.commit()                    # PATCH wins the race

        seen_by_worker.mark_sent()
        with pytest.raises(ConcurrentUpdateError):
            await worker_repo.update(seen_by_worker)  # stale: would have overwritten it


async def test_sqlite_enforces_foreign_keys(client):
    async with AsyncSessionLocal() as s:
        s.add(NotificationModel(user_id=999, title="x", content="y", channel="EMAIL", status="CREATED"))
        with pytest.raises(IntegrityError):
            await s.flush()


# --- delete (soft) --------------------------------------------------------------------

async def rows(model):
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(model))).scalars().all()


async def test_delete_hides_it_but_keeps_the_audit_trail(client):
    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]
    assert (await client.delete(f"/api/notifications/{nid}")).status_code == 204

    # Gone from the API
    assert (await client.get(f"/api/notifications/{nid}")).status_code == 404
    assert (await client.get("/api/notifications")).json() == []
    assert (await client.patch(f"/api/notifications/{nid}", json={"title": "x"})).status_code == 404
    assert (await client.delete(f"/api/notifications/{nid}")).status_code == 404

    # but still in the database, and its delivery was cancelled not sent
    [n] = await rows(NotificationModel)
    assert n.deleted_at is not None and n.status == "CREATED"
    [msg] = await rows(OutboxMessageModel)
    assert msg.status == "CANCELLED"
    await run_worker_once()
    assert await rows(DeliveryAttemptModel) == []


async def test_delete_sent_keeps_its_delivery_history(client):
    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]
    await run_worker_once()
    assert (await client.delete(f"/api/notifications/{nid}")).status_code == 204

    [n] = await rows(NotificationModel)
    assert (n.status, n.deleted_at is not None) == ("SENT", True)
    [attempt] = await rows(DeliveryAttemptModel)
    assert attempt.status == "SUCCESS"
    [msg] = await rows(OutboxMessageModel)
    assert msg.status == "DONE"  # Already processed nothing to cancel


async def test_delete_while_worker_holds_the_message(client):
    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]

    async with AsyncSessionLocal() as s:
        outbox = SQLAlchemyOutboxRepository(s)
        [message] = await outbox.fetch_pending(limit=10)  # worker grabbed it
        assert (await client.delete(f"/api/notifications/{nid}")).status_code == 204
        deliver = DeliverNotification(
            SQLAlchemyNotificationRepository(s), SQLAlchemyDeliveryAttemptRepository(s), build_channel_registry(),
        )
        await _process_message(s, outbox, deliver, message)  # SKIPPED, and must not overwrite CANCELLED

    [msg] = await rows(OutboxMessageModel)
    assert msg.status == "CANCELLED"
    assert await rows(DeliveryAttemptModel) == []


async def test_delete_loses_race_against_worker_with_409(client):
    """API read the row, then the worker market it SENT and committed: the
    delete must not silently overwrite that. The client gets 409 and retries."""
    from fs_notifications_challenge.domain.errors import ConflictError
    
    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]

    async with AsyncSessionLocal() as api_s:
        api_repo = SQLAlchemyNotificationRepository(api_s)
        seen = await api_repo.get(nid)                  # API reeds (version 1)
        await run_worker_once()                         # worker sends + commits (verion 2)
        seen.delete()
        with pytest.raises(ConflictError):
            await api_repo.update(seen)

    assert (await client.delete(f"/api/notifications/{nid}")).status_code == 204  # retyr succeeds


async def test_delete_during_the_provider_call(client):
    """Deleted while the provider call is in flight. The worker's UPDATE fails
    its version check, so it can't un-delete the row or mark it SENT, and the
    cycle survives. Known limit: the provider may already have accepted the 
    message, and that attempt isn't recorded (no DB can roll back an SMS)."""
    from fs_notifications_challenge.application.channel_registry import ChannelRegistry
    from fs_notifications_challenge.infrastructure.channels.email import EmailSender


    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]

    class DeletedMidSend(EmailSender):
        async def send(self, notification):
            assert (await client.delete(f"/api/notifications/{nid}")).status_code == 204
            return await super().send(notification)

    await _process_one_cycle(ChannelRegistry([DeletedMidSend()]), poll_limit=10)

    [n] = await rows(NotificationModel)
    assert (n.status, n.deleted_at is not None) == ("CREATED", True) 
    [msg] = await rows(OutboxMessageModel)
    assert msg.status == "CANCELLED"


async def test_delete_from_the_html_page_redirects_home(client):
    uid = await make_user(client)
    nid = (await client.post("/api/notifications", json=body(uid))).json()["id"]
    response = await client.post(f"/notifications/{nid}/delete")
    assert (response.status_code, response.headers["location"]) == (303, "/")
    assert (await client.get(f"/api/notifications/{uid}")).status_code == 404
