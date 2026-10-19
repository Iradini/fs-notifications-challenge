from datetime import UTC, datetime, timedelta

import hashlib
import logging

import aiosmtplib

import pytest

from fastapi import BackgroundTasks
from sqlalchemy import func, select

from fs_notifications_challenge.application.ports import (
    PasswordHasher,
    PasswordResetMailer,
    PasswordResetTokenRepository,
    ResetTokenService,
    UserRepository
)
from fs_notifications_challenge.application.request_password_reset import RequestPasswordReset
from fs_notifications_challenge.application.reset_password import INVALID_LINK, ResetPassword
from fs_notifications_challenge.domain.errors import DomainError
from fs_notifications_challenge.domain.password_reset import PasswordResetToken
from fs_notifications_challenge.domain.user import User
from fs_notifications_challenge.config import settings
from fs_notifications_challenge.infrastructure.database import AsyncSessionLocal
from fs_notifications_challenge.infrastructure.mailer import (
    ConsolePasswordResetMailer,
    SmtpPasswordResetMailer,
    build_reset_url,
)
from fs_notifications_challenge.infrastructure.models import PasswordResetTokenModel
from fs_notifications_challenge.infrastructure.password_reset_repository import SQLAlchemyPasswordResetTokenRepository
from fs_notifications_challenge.infrastructure.security import Sha256ResetTokenService
from fs_notifications_challenge.interface.background_mailer import BackgroundMailer
from fs_notifications_challenge.interface.dependencies import get_password_reset_mailer
from fs_notifications_challenge.main import app
from tests.test_api import PASSWORD, client, make_user   # noqa: F401    (client is a fixture)

NEW_PASSWORD = "Brand-new-1234"
SENT_ANSWER = "If an account exists with this email, you will receive password reset instructions."


class FakeUsers(UserRepository):
    def __init__(self, *users: User) -> None:
        self.by_id = {u.id: u for u in users}


    async def add(self, user):
        self.by_id[user.id] = user
        return user


    async def get(self, user_id):
        return self.by_id.get(user_id)


    async def get_by_email(self, email):
        return next((u for u in self.by_id.values() if u.email.lower() == email.lower()), None)


    async def update(self, user):
        self.by_id[user.id] = user
        return user


    async def delete(self, user):
        self.by_id.pop(user.id, None)


class FakeTokens(PasswordResetTokenRepository):
    def __init__(self) -> None:
        self.rows: list[PasswordResetToken] = []


    async def add(self, token):
        self.rows.append(token)
        return token


    async def get_by_hash(self, token_hash):
        return next((t for t in self.rows if t.token_hash == token_hash), None)


    async def delete_for_user(self, user_id):
        self.rows = [t for t in self.rows if t.user_id != user_id]


class FakeSecrets(ResetTokenService):
    """Predictable on purpose: the test can name the token it expects."""

    def __init__(self) -> None:
        self.count = 0


    def generate(self):
        self.count += 1
        return f"secret-{self.count}"


    def digest(self, token):
        return f"digest:{token}"


class FakeHasher(PasswordHasher):
    def hash_password(self, password):
        return f"hashed:{password}"


    def verify_password(self, plain_password, hashed_password):
        return hashed_password == f"hashed:{plain_password}" 


class FakeMailer(PasswordResetMailer):
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.fail = False


    async def send_reset_link(self, to_email, token):
        if self.fail:
            raise ConnectionError("SMTP server down")
        self.sent.append((to_email, token))


def _request_case(users, tokens, mailer, secrets=None) -> RequestPasswordReset:
    return RequestPasswordReset(
        users=users, tokens=tokens, secrets=secrets or FakeSecrets(), 
        mailer=mailer, ttl=timedelta(hours=1),
    )


async def test_requesting_for_an_unknown_email_does_nothing_and_does_not_fail():
    tokens, mailer = FakeTokens(), FakeMailer()

    await _request_case(FakeUsers(), tokens, mailer).execute("nobody@example.com")

    assert tokens.rows == [] and mailer.sent == []


async def test_requesting_stores_the_digest_and_mails_the_secret():
    users = FakeUsers(User(id=7, email="test@example.com", password_hash="old"))
    tokens, mailer = FakeTokens(), FakeMailer()

    await _request_case(users, tokens, mailer).execute("TEST@example.com")

    assert mailer.sent == [("test@example.com", "secret-1")]
    [stored] = tokens.rows
    assert stored.user_id == 7
    assert stored.token_hash == "digest:secret-1"           # never the secret itself
    assert not stored.is_expired()


async def test_a_second_request_replaces_the_first_link():
    users = FakeUsers(User(id=7, email="test@example.com", password_hash="old"))
    tokens, mailer = FakeTokens(), FakeMailer()
    case = _request_case(users, tokens, mailer)
    
    await case.execute("test@example.com")
    await case.execute("test@example.com")
    assert [t.token_hash for t in tokens.rows] == ["digest:secret-2"]    


def _reset_case(users, tokens) -> ResetPassword:
    return ResetPassword(users=users, tokens=tokens, secrets=FakeSecrets(), hasher=FakeHasher())


def _live_token(
        user_id: int, secret: str = "s", ttl: timedelta = timedelta(hours=1)
) -> PasswordResetToken:
    return PasswordResetToken.issue(user_id, f"digest:{secret}", ttl)


async def test_resetting_hashes_the_new_password_and_spends_every_token_of_the_user():
    user = User(id=7, email="test@example.com", password_hash="old")
    tokens = FakeTokens()
    tokens.rows = [_live_token(7, "mine"), _live_token(7, "older"), _live_token(8, "someone-else")]

    await _reset_case(FakeUsers(user), tokens).execute("mine", NEW_PASSWORD)

    assert user.password_hash == f"hashed:{NEW_PASSWORD}"       # hashed, never the plain text
    assert [t.user_id for t in tokens.rows] == [8]              # the other user's token is untouched


@pytest.mark.parametrize("scenario", ["unknown", "expired", "user-gone"])
async def test_every_bad_link_gets_the_same_error_and_changes_nothing(scenario):
    user = User(id=7, email="test@example.com", password_hash="old")
    users, tokens = FakeUsers(user), FakeTokens()
    if scenario == "expired":
        tokens.rows = [_live_token(7, "s", ttl=timedelta(seconds=-1))]
    elif scenario == "user-gone":
        tokens.rows = [_live_token(999, "s")]
    else:
        tokens.rows = [_live_token(7, "another")]

    with pytest.raises(DomainError, match=INVALID_LINK):
        await _reset_case(users, tokens).execute("s", NEW_PASSWORD)

    assert user.password_hash == "old"


def test_a_token_expires_at_its_deadline():
    token = PasswordResetToken.issue(user_id=1, token_hash="h", ttl=timedelta(minutes=30))
    assert not token.is_expired()
    assert not token.is_expired(now=token.expires_at - timedelta(seconds=1))
    assert token.is_expired(now=token.expires_at)


def test_a_token_without_a_hash_is_not_a_token():
    with pytest.raises(DomainError):
        PasswordResetToken(user_id=1, token_hash="  ", expires_at=datetime.now(UTC))


async def test_the_repository_gives_back_timezone_aware_datetimes(client):
    uid = await make_user(client)
    async with AsyncSessionLocal() as s:
        repo = SQLAlchemyPasswordResetTokenRepository(s)
        await repo.add(PasswordResetToken.issue(uid, "fresh", timedelta(hours=1)))
        await repo.add(PasswordResetToken.issue(uid, "stale", timedelta(hours=-1)))
        await s.commit()

    async with AsyncSessionLocal() as s:
        repo = SQLAlchemyPasswordResetTokenRepository(s)
        fresh, stale = await repo.get_by_hash("fresh"), await repo.get_by_hash("stale")
        assert await repo.get_by_hash("wissing") is None

    assert fresh.expires_at.tzinfo is not None
    assert fresh.id is not None
    assert not fresh.is_expired() and stale.is_expired()        # would raise TypeError on a naive datetime


def test_the_secret_is_long_random_and_the_digest_is_stable():
    service = Sha256ResetTokenService()
    first, second = service.generate(), service.generate()

    assert first != second and len(first) >= 43                 # 32 random bytes, url-safe base64
    assert service.digest(first) == hashlib.sha256(first.encode()).hexdigest()
    assert service.digest(first) != first


def test_the_reset_url_encodes_the_token():
    assert build_reset_url("http://localhost:8000/", "abc") == "http://localhost:8000/reset-password?token=abc"
    assert build_reset_url("http://x", "a b&c") == "http://x/reset-password?token=a+b%26c"


def _smtp_mailer(**overrides) -> SmtpPasswordResetMailer:
    settings_ = dict(hostname="smtp.example.com", port=2525, username="", password="", start_tls=True,
                     frontend_url="http://localhost:8000", mail_from="noreply@example.com", expires_minutes=60)
    return SmtpPasswordResetMailer(**{**settings_, **overrides})


def test_the_message_carries_the_link_in_text_and_html():
    message = _smtp_mailer().build_message("test@example.com", "tok123")

    assert message["To"] == "test@example.com" and message["From"] == "noreply@example.com"
    assert message["Subject"] == "Reset your password"
    link = "http://localhost:8000/reset-password?token=tok123"
    text, html = message.get_body(("plain",)).get_content(), message.get_body(("html",)).get_content()
    assert link in text and f'href="{link}"' in html
    assert "expires in 1 hour" in text


async def test_smtp_send_passes_the_settings_to_aiosmtplib(monkeypatch):
    calls = []

    async def fake_send(message, **kwargs):
        calls.append((message, kwargs))

    monkeypatch.setattr(aiosmtplib, "send", fake_send)

    await _smtp_mailer(username="user", password="secret").send_reset_link("test@example.com", "tok")
    await _smtp_mailer().send_reset_link("test@example.com", "tok")

    assert calls[0][1] == {"hostname": "smtp.example.com", "port": 2525, "username": "user",
                           "password": "secret", "start_tls": True}
    assert calls[1][1]["username"] is None and calls[1][1]["password"] is None      # "" means no login


async def test_the_console_mailer_logs_the_link_instead_of_sending(caplog):
    mailer = ConsolePasswordResetMailer(frontend_url="http://localhost:8000", mail_from="a@example.com", expires_minutes=60)

    with caplog.at_level(logging.INFO, logger="notifications.mailer"):
        await mailer.send_reset_link("ana@example.com", "tok")
    assert "http://localhost:8000/reset-password?token=tok" in caplog.text


async def test_the_background_mailer_only_queues_until_the_response_is_sent():
    inner, tasks = FakeMailer(), BackgroundTasks()

    await BackgroundMailer(inner, tasks).send_reset_link("test@example.com", "tok")
    assert inner.sent == []                                  # queued, nothing sent yet

    await tasks()                                            # what Starlette does after the response
    assert inner.sent == [("test@example.com", "tok")]


@pytest.fixture
def mailer():
    fake = FakeMailer()
    app.dependency_overrides[get_password_reset_mailer] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_password_reset_mailer, None)


async def _forgot(client, email="owner@example.com"):
    return await client.post("/api/auth/forgot-password", json={"email": email})


async def _reset(client, token, password=NEW_PASSWORD):
    return await client.post("/api/auth/reset-password", json={"token": token, "new_password": password})


async def _can_log_in(client, email, password) -> bool:
    response = await client.post("/api/auth/token", data={"username": email, "password": password})
    return response.status_code == 200


async def test_forgot_password_answers_identically_for_known_and_unknown_emails(client, mailer):
    await make_user(client)

    known, unknown = await _forgot(client), await _forgot(client, "nobody@example.com")

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == {"message": SENT_ANSWER}
    assert [to for to, _ in mailer.sent] == ["owner@example.com"]


async def test_the_database_keeps_the_hash_and_the_email_has_the_secret(client, mailer):
    await make_user(client)
    await _forgot(client)
    [(_, secret)] = mailer.sent

    async with AsyncSessionLocal() as s:
        [row] = (await s.execute(select(PasswordResetTokenModel))).scalars().all()

    assert row.token_hash == hashlib.sha256(secret.encode()).hexdigest()
    assert secret not in row.token_hash


async def test_the_whole_flow_changes_the_password_and_the_link_works_once(client, mailer):
    await make_user(client)
    await _forgot(client)
    [(_, token)] = mailer.sent

    response = await _reset(client, token)

    assert response.status_code == 200
    assert "Password reset successfully" in response.json()["message"]
    assert await _can_log_in(client, "owner@example.com", NEW_PASSWORD)
    assert not await _can_log_in(client, "owner@example.com", PASSWORD)

    again = await _reset(client, token, "Yet-another-pass-1")
    assert again.status_code == 422 and again.json()["detail"] == INVALID_LINK
    assert await _can_log_in(client, "owner@example.com", NEW_PASSWORD)          # the replay changed nothing


async def test_asking_twice_makes_the_first_link_useless(client, mailer):
    await make_user(client)
    await _forgot(client)
    await _forgot(client)
    (_, first), (_, second) = mailer.sent

    assert (await _reset(client, first)).status_code == 422
    assert (await _reset(client, second)).status_code == 200


async def test_an_expired_link_is_refused_and_the_password_stays(client, mailer, monkeypatch):
    monkeypatch.setattr(settings, "reset_token_expire_minutes", -1)      # already expired when issued
    await make_user(client)
    await _forgot(client)
    [(_, token)] = mailer.sent

    response = await _reset(client, token)

    assert response.status_code == 422 and response.json()["detail"] == INVALID_LINK
    assert await _can_log_in(client, "owner@example.com", PASSWORD)


async def test_a_made_up_token_is_refused(client, mailer):
    await make_user(client)
    response = await _reset(client, "not-a-real-token")
    assert response.status_code == 422 and response.json()["detail"] == INVALID_LINK


async def test_a_too_short_password_is_refused_without_spending_the_link(client, mailer):
    await make_user(client)
    await _forgot(client)
    [(_, token)] = mailer.sent

    assert (await _reset(client, token, "short")).status_code == 422
    assert (await _reset(client, token)).status_code == 200            # same link, now with a good password


@pytest.mark.parametrize(("path", "payload"), [
    ("/api/auth/forgot-password", {"email": "not-an-email"}),
    ("/api/auth/forgot-password", {}),
    ("/api/auth/forgot-password", {"email": "a@example.com", "extra": 1}),
    ("/api/auth/reset-password", {"new_password": NEW_PASSWORD}),
    ("/api/auth/reset-password", {"token": "", "new_password": NEW_PASSWORD}),
    ("/api/auth/reset-password", {"token": "t", "new_password": NEW_PASSWORD, "email": "x@example.com"}),
], ids=["bad-email", "no-email", "unknown-field", "no-token", "empty-token", "unknown-field-reset"])
async def test_malformed_bodies_are_422(client, mailer, path, payload):
    response = await client.post(path, json=payload)
    assert response.status_code == 422, response.text
    assert mailer.sent == []


async def test_resetting_one_account_leaves_the_others_alone(client, mailer):
    await make_user(client, "ana@example.com")
    await make_user(client, "bea@example.com")
    await _forgot(client, "ana@example.com")
    await _forgot(client, "bea@example.com")
    (_, ana_token), (_, bea_token) = mailer.sent

    assert (await _reset(client, ana_token)).status_code == 200

    assert await _can_log_in(client, "bea@example.com", PASSWORD)
    assert (await _reset(client, bea_token)).status_code == 200            # Bea's link is still alive


async def test_a_mail_server_that_is_down_does_not_change_the_answer(client, mailer, caplog):
    await make_user(client)
    mailer.fail = True

    with caplog.at_level(logging.ERROR, logger="notifications.mailer"):
        response = await _forgot(client)

    assert response.status_code == 202 and response.json() == {"message": SENT_ANSWER}
    assert "Could not send the password reset email" in caplog.text


async def test_deleting_an_account_erases_its_reset_tokens(client, mailer):
    uid = await make_user(client)
    await _forgot(client)
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(func.count()).select_from(PasswordResetTokenModel))).scalar_one() == 1

    response = await client.request("DELETE", f"/api/users/{uid}", json={"password": PASSWORD})

    assert response.status_code == 204, response.text
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(func.count()).select_from(PasswordResetTokenModel))).scalar_one() == 0


async def test_the_pages_exist_and_the_reset_page_hides_its_url_from_third_parties(client):
    forgot = await client.get("/forgot-password")
    reset = await client.get("/reset-password?token=abc")
    login_page = await client.get("/login")

    assert forgot.status_code == 200 and "Send Reset Link" in forgot.text
    assert reset.status_code == 200 and "Reset Password" in reset.text
    assert reset.headers["referrer-policy"] == "no-referrer"
    assert "/forgot-password" in login_page.text