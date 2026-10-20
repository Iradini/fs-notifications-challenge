"""PUT /api/users/{id}/password and DELETE /api/users/{id} (the account itself).

Reuses the `client` fixture and the helpers from test_api.py so there is one place
that set up the database and the logged in client."""

import pytest
from sqlalchemy import func, select

from fs_notifications_challenge.domain.errors import DomainError
from fs_notifications_challenge.domain.user import User
from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal
from fs_notifications_challenge.infrastructure.models import (
    DeliveryAttemptModel,
    NotificationModel,
    OutboxMessageModel,
    UserModel,
    UserProfileModel,
)
from tests.conftest import PASSWORD, body, client, login, make_user, run_worker_once    # noqa: F401 

NEW_PASSWORD = "Another1234+"


async def _token_status(client, email: str, password: str) -> int:
    response = await client.post("/api/auth/token", data={"username": email, "password": password})
    return response.status_code


async def _count(model) -> int:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(func.count()).select_from(model))).scalar_one()


async def _delete_account(client, user_id: int, password: str):
    # httpx's .delete() takes no body, and this endpoint asks for the password in one
    return await client.request("DELETE", f"/api/users/{user_id}", json={"password": password}) 


# --- the entity ----------------------------------------------------------------------------------

async def test_change_password_replaces_the_hash():
    user = User(email="test@example.com", password_hash="old", id=1)
    user.change_password("new-hash")
    assert user.password_hash == "new-hash"


async def test_a_blank_hash_is_rejected_and_nothing_changes():
    user = User(email="test@example.com", password_hash="old", id=1)
    with pytest.raises(DomainError):
        user.change_password("  ")
    assert user.password_hash == "old"


# --- change password -----------------------------------------------------------------------------

async def test_the_new_password_works_and_the_old_one_does_not(client):
    uid = await make_user(client)
    
    response = await client.put(
        f"/api/users/{uid}/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204, response.text
    assert await _token_status(client, "owner@example.com", NEW_PASSWORD) == 200
    assert await _token_status(client, "owner@example.com", PASSWORD) == 401


async def test_a_wrong_current_password_is_422_not_401(client):
    """401 would make the page think the session is over and bounce to /login."""
    uid = await make_user(client)

    response = await client.put(
        f"/api/users/{uid}/password", json={"current_password": "Not-my-password", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Current password is incorrect."
    assert await _token_status(client, "owner@example.com", PASSWORD) == 200   # unchanged
    assert await _token_status(client, "owner@example.com", NEW_PASSWORD) == 401


async def test_the_new_password_must_differ_from_the_current_one(client):
    uid = await make_user(client)
    response = await client.put(
        f"/api/users/{uid}/password", json={"current_password": PASSWORD, "new_password": PASSWORD},
    )
    assert response.status_code == 422
    assert "different" in response.json()["detail"]


@pytest.mark.parametrize("payload", [
    {"current_password": PASSWORD, "new_password": "short"},             # under 8 characters
    {"current_password": "", "new_password": NEW_PASSWORD},              # empty current
    {"new_password": NEW_PASSWORD},                                      # current missing
    {"current_password": PASSWORD},                                      # new missing
    {"current_password": PASSWORD, "new_password": NEW_PASSWORD, "email": "x@example.com"},  # unknown field
], ids=["short", "empty-current", "no-current", "no-new", "unknown-field"])
async def test_invalid_password_bodies_are_422(client, payload):
    uid = await make_user(client)
    response = await client.put(f"/api/users/{uid}/password", json=payload)
    assert response.status_code == 422, response.text
    assert await _token_status(client, "owner@example.com", PASSWORD) == 200


async def test_you_cannot_change_someone_else_password(client):
    john = await make_user(client, "john.doe@example.com")
    await make_user(client, "ana@example.com")

    response = await client.put(
        f"/api/users/{john}/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 404
    assert await _token_status(client, "john.doe@example.com", PASSWORD) == 200


async def test_change_password_requires_a_token(client):
    uid = await make_user(client)
    client.headers.pop("Authorization")
    response = await client.put(
        f"/api/users/{uid}/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_the_session_survives_a_password_change(client):
    """Token are stateless JWTs: changing the password does not revokes them."""
    uid = await make_user(client)
    await client.put(f"/api/users/{uid}/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert (await client.get(f"/api/auth/me")).status_code == 200


# --- delete account -------------------------------------------------------------------------------

async def test_delete_account_with_the_right_password(client):
    uid = await make_user(client)

    response = await _delete_account(client, uid, PASSWORD)

    assert response.status_code == 204, response.text
    # The old token points at nobody now, and the credentials no longer log in
    assert (await client.get("/api/auth/me")).status_code == 401
    assert await _token_status(client, "owner@example.com", PASSWORD) == 401
    assert await _count(UserModel) == 0
    # and the email is free to register again
    again = await client.post("/api/users", json={"email": "owner@example.com", "password": PASSWORD})
    assert again.status_code == 201


async def test_a_wrong_password_deletes_nothing(client):
    uid = await make_user(client)

    response = await _delete_account(client, uid, "Not-my-password")

    assert response.status_code == 422   # not 401: the page would bounce to /login
    assert response.json()["detail"] == "Incorrect password."
    assert (await client.get("/api/auth/me")).status_code == 200
    assert await _count(UserModel) == 1


@pytest.mark.parametrize("payload", [
    {},
    {"password": ""},
    {"password": PASSWORD, "confirm": True},
], ids=["no-password", "empty-password", "unknown-filed"])
async def test_invalid_delete_bodies_are_422(client, payload):
    uid = await make_user(client)
    response = await client.request("DELETE", f"/api/users/{uid}", json=payload)
    assert response.status_code == 422, response.text
    assert await _count(UserModel) == 1


async def test_you_cannot_delete_someone_else_account(client):
    jane = await make_user(client, "jane.doe@example.com")
    await make_user(client, "ana@example.com")

    response = await _delete_account(client, jane, PASSWORD)
    
    assert response.status_code == 404
    assert await _count(UserModel) == 2


async def test_delete_account_requires_a_token(client):
    uid = await make_user(client)
    client.headers.pop("Authorization")
    response = await _delete_account(client, uid, PASSWORD)
    assert response.status_code == 401
    assert await _count(UserModel) == 1


async def test_deleting_an_account_erases_everything_of_it_and_nothing_else(client):
    # Jane: a contact profile and three notifications. Two get delivered by the worker
    # (so they have delivered attempts and DONE outbox rows), one of those is then 
    # soft-deleted, and the last one is still waiting in the outbbox.
    jane = await make_user(client, "jane.doe@example.com")
    await client.patch(f"/api/users/{jane}", json={"profile": {"email": "jane.contact@example.com"}})
    first = (await client.post("/api/notifications", json=body(title="First"))).json()
    await client.post("/api/notifications", json=body(title="Second"))
    await run_worker_once()
    assert (await client.delete(f"/api/notifications/{first['id']}")).status_code == 204

    # Ana: one delived notification. Her rows must survive 
    ana = await make_user(client, "ana@example.com")
    await client.post("/api/notifications", json=body(title="Ana's"))
    await run_worker_once()

    await login(client, "jane.doe@example.com")
    await client.post("/api/notifications", json=body(title="Still pending"))

    async with AsyncSessionLocal() as s:
        jane_notifications = select(NotificationModel.id).where(NotificationModel.user_id == jane)
        before = {
            "notifications": (await s.execute(
                select(func.count()).select_from(NotificationModel).where(NotificationModel.user_id == jane))).scalar_one(),
            "attempts": (await s.execute(
                select(func.count()).select_from(DeliveryAttemptModel)
                .where(DeliveryAttemptModel.notification_id.in_(jane_notifications)))).scalar_one(),
            "outbox": (await s.execute(
                select(func.count()).select_from(OutboxMessageModel)
                .where(OutboxMessageModel.notification_id.in_(jane_notifications)))).scalar_one(),
        }
    # The scenario really has something to erase, soft-deleted rows included
    assert before == {"notifications": 3, "attempts": 2, "outbox": 3}
    assert await _count(UserProfileModel) == 1

    assert (await _delete_account(client, jane, PASSWORD)).status_code == 204

    async with AsyncSessionLocal() as s:
        assert [u.id for u in (await s.execute(select(UserModel))).scalars()] == [ana]
        notifications = list((await s.execute(select(NotificationModel))).scalars())
        assert [n.title for n in notifications] == ["Ana's"]
        assert {a.notification_id for a in (await s.execute(select(DeliveryAttemptModel))).scalars()} == { 
            notifications[0].id,
        }
        assert {m.notification_id for m in (await s.execute(select(OutboxMessageModel))).scalars()} == {
            notifications[0].id,
        }
        assert (await s.execute(select(UserProfileModel))).scalars().all() == [] 