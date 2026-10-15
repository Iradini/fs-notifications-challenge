"""DELETE /api/users/{id}/profile.

Reuses the `client` fixture and the make_user/login helpers from test_api.py so
there is one place that sets up the database and the logged-in client."""

from sqlalchemy import select

from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal
from fs_notifications_challenge.infrastructure.models import UserModel, UserProfileModel
from tests.test_api import client, login, make_user  # noqa: F401  (client is a fixture)


async def _profile_rows() -> list[UserProfileModel]:
    async with AsyncSessionLocal() as s:
        return list((await s.execute(select(UserProfileModel))).scalars())


async def test_delete_profile_removes_the_row_and_keeps_the_user(client):
    uid = await make_user(client)
    await client.patch(f"/api/users/{uid}", json={"profile": {"phone": "+598 99 123 456"}})

    assert (await client.delete(f"/api/users/{uid}/profile")).status_code == 204

    # The row is gone, not blanked: an all-empty profile is invalid in the domain
    assert await _profile_rows() == []
    # ...and the user still loads, logs in and has no profile
    me = await client.get(f"/api/users/{uid}")
    assert me.status_code == 200
    assert me.json()["profile"] is None
    assert (await client.get("/api/auth/me")).status_code == 200
    await login(client)
    async with AsyncSessionLocal() as s:
        assert (await s.get(UserModel, uid)).email == "owner@example.com"


async def test_deleting_a_profile_that_does_not_exist_is_404(client):
    uid = await make_user(client)
    response = await client.delete(f"/api/users/{uid}/profile")
    assert response.status_code == 404
    assert "no profile" in response.json()["detail"]


async def test_a_deleted_profile_can_be_created_again(client):
    uid = await make_user(client)
    await client.patch(f"/api/users/{uid}", json={"profile": {"phone": "+598 99 123 456"}})
    await client.delete(f"/api/users/{uid}/profile")

    again = await client.patch(f"/api/users/{uid}", json={"profile": {"email": "new@example.com"}})
    assert again.status_code == 200
    assert again.json()["profile"] == {"email": "new@example.com"}
    assert len(await _profile_rows()) == 1


async def test_you_cannot_delete_someone_elses_profile(client):
    ana = await make_user(client, "ana@example.com")
    await client.patch(f"/api/users/{ana}", json={"profile": {"phone": "+598 99 123 456"}})

    await make_user(client, "bea@example.com")    # the client now acts as Bea
    # same 404 as a user that doesn't exist, so ids can't be probed
    assert (await client.delete(f"/api/users/{ana}/profile")).status_code == 404

    await login(client, "ana@example.com")
    assert (await client.get(f"/api/users/{ana}")).json()["profile"] == {"phone": "+59899123456"}


async def test_delete_profile_requires_a_token(client):
    uid = await make_user(client)
    client.headers.pop("Authorization")
    response = await client.delete(f"/api/users/{uid}/profile")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
