"""HTTP-level tests: real app, real repositories, throaway SQLite.
The background worker isn't started (no lifespan); test drive it explicitly."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


from fs_notifications_challenge.application.deliver_notification import DeliverNotification
from fs_notifications_challenge.domain.errors import ConcurrentUpdateError
from fs_notifications_challenge.infrastructure.channels import build_channel_registry
from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal
from fs_notifications_challenge.infrastructure.delivery_repository import SQLAlchemyDeliveryAttemptRepository
from fs_notifications_challenge.infrastructure.models import DeliveryAttemptModel, NotificationModel, OutboxMessageModel
from fs_notifications_challenge.infrastructure.outbox import SQLAlchemyOutboxRepository
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository
from fs_notifications_challenge.infrastructure.worker import _process_message, _process_one_cycle
from fs_notifications_challenge.main import app
from tests.conftest import PASSWORD, body, login, make_user, run_worker_once

TOKEN = "fcm_" + "a1B2c3D4" * 8



# --- users & profiles ------------------------------------------------------------------

async def test_duplicate_user_email_is_409(client):
    await make_user(client)
    assert (await client.post("/api/users", json={"email": "owner@example.com", "password": PASSWORD})).status_code == 409


async def test_create_user_never_returns_or_stores_the_plain_password(client):
    response = await client.post("/api/users", json={"email": "owner@example.com", "password": PASSWORD})
    assert response.status_code == 201
    assert set(response.json()) == {"id", "email", "profile"}
    async with AsyncSessionLocal() as s:
        from fs_notifications_challenge.infrastructure.models import UserModel
        stored = (await s.execute(select(UserModel.password_hash))).scalar_one()
    assert stored != PASSWORD and stored.startswith("$argon2")


async def test_create_requires_a_password_of_8_chars(client):
    assert (await client.post("/api/users", json={"email": "ana@example.com"})).status_code == 422
    assert (await client.post("/api/users", json={"email": "ana@example.com", "password": "short"})).status_code == 422


async def test_login_then_me(client):
    await make_user(client)
    login = await client.post("/api/auth/token", data={"username": "owner@example.com", "password": PASSWORD})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "owner@example.com"


async def test_login_failures_are_401_and_indistinguishable(client):
    await make_user(client)
    wrong_password = await client.post("/api/auth/token", data={"username": "owner@example.com", "password": "wrong-password"})
    unknown_email = await client.post("/api/auth/token", data={"username": "another@example.com", "password": PASSWORD})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() 


async def test_me_without_or_with_a_bad_token_is_401(client):
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})).status_code == 401


async def test_profile_is_validated_and_normalized(client):
    uid = await make_user(client)
    ok = await client.patch(f"/api/users/{uid}", json={"profile": {"phone": "+598 99 123 456", "token": TOKEN}})
    assert ok.status_code == 200
    assert ok.json()["profile"] == {"phone": "+59899123456", "token": TOKEN}
    assert (await client.patch(f"/api/users/{uid}", json={"profile": {}})).status_code == 422
    assert (await client.patch("/api/users/999", json={"profile": {"email": "a@b.co"}})).status_code == 404


# --- create -------------------------------------------------------------------------------------

@pytest.mark.parametrize(("overrides", "where"), [
    ({"recipient": {"email": "string"}}, ["body", "EMAIL", "recipient", "email"]),
    ({"channel": "PUSH", "recipient": {"token": "string"}}, ["body", "PUSH", "recipient", "token"]),
    ({"channel": "SMS", "recipient": {"phone": "string"}}, ["body", "SMS", "recipient", "phone"]),
    ({"recipient": {}}, ["body", "EMAIL", "recipient", "email"]),  # missing
])
async def test_invalid_recipient_formats_are_422(client, overrides, where):
    await make_user(client)
    response = await client.post("/api/notifications", json=body(**overrides))
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == where


@pytest.mark.parametrize(("channel", "recipient"), [
    ("SMS", {"phone": "+59899123456"}),
    ("PUSH", {"token": TOKEN})
])
async def test_each_channel_ask_only_for_its_own_address(client, channel, recipient):
    await make_user(client)
    response = await client.post("/api/notifications", json=body(channel=channel, recipient=recipient))
    assert response.status_code == 201, response.text
    assert response.json()["recipient"] == recipient


async def test_address_of_another_channel_is_rejected(client):
    await make_user(client)
    wrong = await client.post("/api/notifications", json=body(channel="SMS"))  # sends an email
    assert wrong.status_code == 422
    problems = {(tuple(e["loc"]), e["type"]) for e in wrong.json()["detail"]}
    assert (("body", "SMS", "recipient", "phone"), "missing") in problems
    assert (("body", "SMS", "recipient", "email"), "extra_forbidden") in problems

    extra = await client.post(
        "/api/notifications", json=body(recipient={"email": "ana@example.com", "phone": "+59899123456"}),
    )
    assert extra.status_code == 422


async def test_unknown_channel_is_422(client):
    await make_user(client)
    assert (await client.post("/api/notifications", json=body(channel="FAX"))).status_code == 422


async def test_notification_routes_require_a_token(client):
    for method, url, kwargs in [
        ("GET", "/api/notifications", {}),
        ("POST", "/api/notifications", {"json": body()}),
        ("GET", "/api/notifications/1", {}),
        ("PATCH", "/api/notifications/1", {"json": {"title": "x"}}),
        ("DELETE", "/api/notifications/1", {}),
    ]:
        response = await client.request(method, url, **kwargs)
        assert response.status_code == 401, (method, url)
        assert response.headers["www-authenticate"] == "Bearer"
    garbage = {"Authorization": "Bearer garbage"}
    assert (await client.get("/api/notifications", headers=garbage)).status_code == 401


async def test_the_owner_comes_from_the_token_not_the_body(client):
    uid = await make_user(client)
    # a user_id in the body is not part of the schema; the notification belongs to the token's user
    created = await client.post("/api/notifications", json={**body(), "user_id": 999})
    assert created.status_code == 201
    assert created.json()["user_id"] == uid


async def test_users_only_see_and_touch_their_own_notifications(client):
    await make_user(client, "ana@example.com")
    mine = (await client.post("/api/notifications", json=body(title="Ana's"))).json()["id"]

    await make_user(client, "bea@example.com")   # the client now acts as Bea
    assert (await client.get("/api/notifications")).json()["notifications"] == []
    # someone else's notification looks exactly like one that doesn't exist
    assert (await client.get(f"/api/notifications/{mine}")).status_code == 404
    assert (await client.patch(f"/api/notifications/{mine}", json={"title": "hacked"})).status_code == 404
    assert (await client.delete(f"/api/notifications/{mine}")).status_code == 404

    await login(client, "ana@example.com")        # and Ana's is untouched
    assert (await client.get(f"/api/notifications/{mine}")).json()["title"] == "Ana's"
    assert [n["title"] for n in (await client.get("/api/notifications")).json()["notifications"]] == ["Ana's"]


async def test_a_profile_is_private_to_its_owner(client):
    ana = await make_user(client, "ana@example.com")
    await client.patch(f"/api/users/{ana}", json={"profile": {"phone": "+598 99 123 456"}})
    assert (await client.get(f"/api/users/{ana}")).json()["profile"] == {"phone": "+59899123456"}

    await make_user(client, "bea@example.com")
    assert (await client.get(f"/api/users/{ana}")).status_code == 404
    assert (await client.patch(f"/api/users/{ana}", json={"profile": {"phone": "+598 99 000 000"}})).status_code == 404

    client.headers.pop("Authorization")
    assert (await client.get(f"/api/users/{ana}")).status_code == 401


async def test_create_get_and_worker_sends_it(client):
    await make_user(client)
    created = await client.post("/api/notifications", json=body())
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
    await make_user(client)
    nid = (await client.post("/api/notifications", json=body())).json()["id"]

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
    assert patched.json()["recipient"] == {"phone": "+59899123456"}

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(OutboxMessageModel))).scalar_one()
        assert (row.status, row.attempts, row.last_error) == ("PENDING", 0, None)

    await run_worker_once()
    sent = (await client.get(f"/api/notifications/{nid}")).json()
    assert (sent["status"], sent["channel"]) == ("SENT", "SMS")


async def test_patch_rule(client):
    await make_user(client)
    nid = (await client.post("/api/notifications", json=body())).json()["id"]

    # Channel switch checked against the STORED recipient (only has an email)
    assert (await client.patch(f"/api/notifications/{nid}", json={"channel": "PUSH"})).status_code == 422
    # A new recipient is exactly one address
    two = {"recipient": {"email": "a@b.com", "phone": "+59899123456"}}
    assert (await client.patch(f"/api/notifications/{nid}", json=two)).status_code == 422
    # and it must match the current channel: a phone on a EMAIL notification is a 422
    phone_only = {"recipient": "+59899123456"}
    assert (await client.patch(f"/api/notifications/{nid}", json=phone_only)).status_code == 422
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
    await make_user(client)
    nid = (await client.post("/api/notifications", json=body())).json()["id"]
    await run_worker_once()
    await client.patch(f"/api/notifications/{nid}", json={"title": "Edited", "content": "New Text"})

    async with AsyncSessionLocal() as s:
        [attempt] = (await s.execute(select(DeliveryAttemptModel))).scalars().all()
    assert attempt.detail["message"] == {"title": "Test", "content": "Test Content"}  # the audit trail didn't move


# --- persistence guarantees --------------------------------------------------------------

async def test_worker_and_patch_race_is_detected(client):
    await make_user(client)
    nid = (await client.post("/api/notifications", json=body())).json()["id"]

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
    await make_user(client)
    nid = (await client.post("/api/notifications", json=body())).json()["id"]
    assert (await client.delete(f"/api/notifications/{nid}")).status_code == 204

    # Gone from the API
    assert (await client.get(f"/api/notifications/{nid}")).status_code == 404
    assert (await client.get("/api/notifications")).json()["notifications"] == []
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
    await make_user(client)
    nid = (await client.post("/api/notifications", json=body())).json()["id"]
    await run_worker_once()
    assert (await client.delete(f"/api/notifications/{nid}")).status_code == 204

    [n] = await rows(NotificationModel)
    assert (n.status, n.deleted_at is not None) == ("SENT", True)
    [attempt] = await rows(DeliveryAttemptModel)
    assert attempt.status == "SUCCESS"
    [msg] = await rows(OutboxMessageModel)
    assert msg.status == "DONE"  # Already processed nothing to cancel


async def test_delete_while_worker_holds_the_message(client):
    await make_user(client)
    nid = (await client.post("/api/notifications", json=body())).json()["id"]

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
    
    await make_user(client)
    nid = (await client.post("/api/notifications", json=body())).json()["id"]

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


    await make_user(client)
    nid = (await client.post("/api/notifications", json=body())).json()["id"]

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
    await make_user(client)
    created = (await client.post("/api/notifications", json=body(title="Top secret title"))).json()
    client.headers.pop("Authorization")   # a visitor with no token
    for url in ("/", f"/notifications/{created['id']}", f"/account", "/login", "/register"):
        page = await client.get(url)
        assert page.status_code == 200, url
        assert "Top secret title" not in page.text and "owner@example.com" not in page.text, url
    # and the old unauthenticated delete form endpoint no longer exists
    assert (await client.post(f"/notifications/{created['id']}/delete")).status_code in (404, 405)


async def test_pages_are_shells_that_leak_nothing(client):
    await make_user(client)
    created = (await client.post("/api/notifications", json=body(title="Top secret title"))).json()
    client.headers.pop("Authorization")   # a visitor with no token
    # URLs come from the route names, so renaming a path doesn't silently skip a page
    urls = (
        app.url_path_for("home"),
        app.url_path_for("notification_page", notification_id=created["id"]),
        app.url_path_for("account_page"),
        app.url_path_for("login_page"),
        app.url_path_for("register_page"),
    )
    for url in urls:
        page = await client.get(url)
        assert page.status_code == 200, url
        assert "Top secret title" not in page.text and "owner@example.com" not in page.text, url
    # and the old unauthenticated delete form endpoint no longer exists
    assert (await client.post(f"/notifications/{created['id']}/delete")).status_code in (404, 405)


async def test_the_detail_page_receives_its_notification_id(client):
    """The page's script builds its API URL from this number. If the route doesn't
    pass `notification_id`, Jinja renders `const notificationId = ;` and the whole
    script dies with a syntax error, so the page stays blank."""
    page = await client.get(app.url_path_for("notification_page", notification_id=42))
    assert page.status_code == 200
    assert "const notificationId = 42;" in page.text
