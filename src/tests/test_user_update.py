"""PATCH /api/users/{id}  (change the login email and/or the contact details)
plus the unit tests of the behaviour the User entity owns.

Reuses the `client` fixture and the make_user/login helpers from test_api.py so
there is one place that sets up the database and the logged-in client."""

import pytest
from sqlalchemy import select

from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import ConflictError, DomainError
from fs_notifications_challenge.domain.user import User, UserProfile
from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal
from fs_notifications_challenge.infrastructure.models import UserModel, UserProfileModel
from fs_notifications_challenge.infrastructure.user_repository import SQLAlchemyUserRepository
from tests.conftest import PASSWORD, client, login, make_user  # noqa: F401  (client is a fixture)

PHONE = "+598 99 123 456"          # stored as +59899123456


async def _profile_rows() -> list[UserProfileModel]:
    async with AsyncSessionLocal() as s:
        return list((await s.execute(select(UserProfileModel))).scalars())


# --- the entity owns its behaviour (no database, no HTTP) ---------------------------

def test_change_email_strips_and_replaces():
    user = User(email="old@example.com", password_hash="x", id=1)
    user.change_email("  new@example.com ")
    assert user.email == "new@example.com"


def test_a_blank_email_is_rejected_and_nothing_changes():
    user = User(email="old@example.com", password_hash="x", id=1)
    with pytest.raises(DomainError, match="cannot be blank"):
        user.change_email("   ")
    assert user.email == "old@example.com"


def test_set_profile_creates_the_profile_for_this_user():
    user = User(email="a@example.com", password_hash="x", id=7)
    user.set_profile(ContactInfo(phone="+59899123456"))
    assert user.profile == UserProfile(user_id=7, contact=ContactInfo(phone="+59899123456"))


def test_set_profile_replaces_the_whole_contact():
    user = User(email="a@example.com", password_hash="x", id=7)
    user.set_profile(ContactInfo(phone="+59899123456", email="c@example.com"))
    first = user.profile
    user.set_profile(ContactInfo(email="d@example.com"))
    assert user.profile is first                                   # same profile, new contact
    assert user.profile.contact == ContactInfo(email="d@example.com")   # the phone is gone


def test_an_empty_contact_is_rejected_and_the_profile_is_untouched():
    user = User(email="a@example.com", password_hash="x", id=7)
    user.set_profile(ContactInfo(phone="+59899123456"))
    with pytest.raises(DomainError, match="requires at least one"):
        user.set_profile(ContactInfo())
    assert user.profile.contact == ContactInfo(phone="+59899123456")


def test_remove_profile_is_idempotent():
    user = User(email="a@example.com", password_hash="x", id=7)
    user.set_profile(ContactInfo(phone="+59899123456"))
    user.remove_profile()
    assert user.profile is None
    user.remove_profile()           # nothing to remove: no error
    assert user.profile is None


def test_a_new_profile_cannot_be_empty_either():
    user = User(email="a@example.com", password_hash="x", id=7)
    with pytest.raises(DomainError):
        user.set_profile(ContactInfo())
    assert user.profile is None


# --- PATCH /api/users/{id} -----------------------------------------------------------

async def test_change_only_the_email(client):
    uid = await make_user(client, "old@example.com")

    response = await client.patch(f"/api/users/{uid}", json={"email": "new@example.com"})

    assert response.status_code == 200, response.text
    assert response.json() == {"id": uid, "email": "new@example.com", "profile": None}
    # The token carries the id, not the email: the session survives the change...
    assert (await client.get("/api/auth/me")).json()["email"] == "new@example.com"
    # ...and from now on you log in with the new address, not the old one
    await login(client, "new@example.com")
    old = await client.post("/api/auth/token", data={"username": "old@example.com", "password": PASSWORD})
    assert old.status_code == 401


async def test_change_only_the_contact_creates_the_profile(client):
    uid = await make_user(client)

    response = await client.patch(f"/api/users/{uid}", json={"profile": {"phone": PHONE}})

    assert response.status_code == 200, response.text
    assert response.json()["email"] == "owner@example.com"
    assert response.json()["profile"] == {"phone": "+59899123456"}
    assert len(await _profile_rows()) == 1


async def test_change_both_at_once(client):
    uid = await make_user(client)

    response = await client.patch(
        f"/api/users/{uid}", json={"email": "new@example.com", "profile": {"email": "contact@example.com"}},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"id": uid, "email": "new@example.com", "profile": {"email": "contact@example.com"}}
    stored = (await client.get(f"/api/users/{uid}")).json()
    assert stored == response.json()


async def test_the_profile_replaces_the_whole_contact(client):
    uid = await make_user(client)
    await client.patch(f"/api/users/{uid}", json={"profile": {"phone": PHONE, "email": "contact@example.com"}})

    response = await client.patch(f"/api/users/{uid}", json={"profile": {"email": "other@example.com"}})

    assert response.json()["profile"] == {"email": "other@example.com"}    # the phone is gone
    rows = await _profile_rows()
    assert len(rows) == 1 and rows[0].phone is None


async def test_an_email_that_is_taken_is_409_and_nothing_is_applied(client):
    await make_user(client, "ana@example.com")
    bea = await make_user(client, "bea@example.com")        # the client now acts as Bea

    response = await client.patch(
        f"/api/users/{bea}", json={"email": "ana@example.com", "profile": {"phone": PHONE}},
    )

    assert response.status_code == 409
    # All or nothing: the contact in the same request was not applied either
    stored = (await client.get(f"/api/users/{bea}")).json()
    assert stored == {"id": bea, "email": "bea@example.com", "profile": None}
    assert await _profile_rows() == []


async def test_the_taken_check_ignores_case(client):
    await make_user(client, "ana@example.com")
    bea = await make_user(client, "bea@example.com")

    response = await client.patch(f"/api/users/{bea}", json={"email": "Ana@Example.com"})

    assert response.status_code == 409


async def test_sending_your_own_email_is_not_a_conflict(client):
    uid = await make_user(client)

    # same address + a new contact: the email is yours, so it must not collide with itself
    same = await client.patch(
        f"/api/users/{uid}", json={"email": "owner@example.com", "profile": {"phone": PHONE}},
    )
    assert same.status_code == 200, same.text
    assert same.json()["profile"] == {"phone": "+59899123456"}

    # changing only the capitalisation of your own address is allowed too
    recased = await client.patch(f"/api/users/{uid}", json={"email": "Owner@example.com"})
    assert recased.status_code == 200, recased.text
    assert recased.json()["email"] == "Owner@example.com"
    await login(client, "owner@example.com")      # lookups are case-insensitive


@pytest.mark.parametrize("payload", [
    {},                                         # nothing to change
    {"email": None},                            # null is not "leave it"; leaving it out is
    {"profile": None},                          # removing the profile is DELETE /profile
    {"profile": {}},                            # a profile needs at least one address
    {"email": "not-an-email"},
    {"email": "new@example.com", "password": "Another1234+"},   # unknown field
], ids=["empty", "null-email", "null-profile", "empty-profile", "bad-email", "unknown-field"])
async def test_invalid_bodies_are_422(client, payload):
    uid = await make_user(client)
    response = await client.patch(f"/api/users/{uid}", json=payload)
    assert response.status_code == 422, response.text


async def test_you_cannot_edit_someone_else(client):
    ana = await make_user(client, "ana@example.com")
    await make_user(client, "bea@example.com")        # the client now acts as Bea

    # same 404 as a user that doesn't exist, so ids can't be probed
    response = await client.patch(f"/api/users/{ana}", json={"email": "hacked@example.com"})
    assert response.status_code == 404

    await login(client, "ana@example.com")            # Ana's email did not change
    assert (await client.get(f"/api/users/{ana}")).json()["email"] == "ana@example.com"


async def test_patch_user_requires_a_token(client):
    uid = await make_user(client)
    client.headers.pop("Authorization")
    response = await client.patch(f"/api/users/{uid}", json={"email": "new@example.com"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


# --- the database has the last word on uniqueness -----------------------------------

async def test_the_repository_turns_a_unique_violation_into_a_conflict(client):
    """Two requests can pass the use case's check at the same moment; the UNIQUE
    constraint then fails at flush and must surface as ConflictError (-> 409),
    not as a raw IntegrityError (-> 500)."""
    ana = await make_user(client, "ana@example.com")
    await make_user(client, "bea@example.com")

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyUserRepository(session)
        user = await repository.get(ana)
        user.email = "bea@example.com"          # skip the use case's check on purpose
        with pytest.raises(ConflictError):
            await repository.update(user)
        await session.rollback()

    async with AsyncSessionLocal() as session:
        assert (await session.get(UserModel, ana)).email == "ana@example.com"


async def test_update_makes_the_profile_row_match_the_entity(client):
    """No use case removes a profile through update() today (DELETE /profile
    does), but the port promises "create, replace or remove to match"."""
    uid = await make_user(client)
    await client.patch(f"/api/users/{uid}", json={"profile": {"phone": PHONE}})

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyUserRepository(session)
        user = await repository.get(uid)
        user.profile = None
        await repository.update(user)
        await session.commit()

    assert await _profile_rows() == []
    assert (await client.get(f"/api/users/{uid}")).json()["profile"] is None
