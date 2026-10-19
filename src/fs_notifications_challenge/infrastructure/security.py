from datetime import UTC, datetime, timedelta

import hashlib 
import jwt
import secrets
from pwdlib import PasswordHash

from fs_notifications_challenge.application.ports import PasswordHasher, ResetTokenService, TokenService
from fs_notifications_challenge.domain.errors import AuthenticationError


class Argon2PasswordHasher(PasswordHasher):
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()

    
    def hash_password(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self._hasher.verify(plain_password, hashed_password)


class JwtTokenService(TokenService):
    """Config comes in through the constructor (not read from `settings` here),
    so tests can build one with short or negative lifetime."""

    def __init__(self, secret: str, algorith: str = "HS256", expires_minutes: int = 30) -> None:
        self._secret = secret
        self._algorithm = algorith
        self._ttl = timedelta(minutes=expires_minutes)


    def issue(self, user_id: int) -> str:
        now = datetime.now(UTC)
        claims = {"sub": str(user_id), "iat": now, "exp": now + self._ttl} # JWT requires `sub` to be a string
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    def verify_access_token(self, token: str) -> int:
        """Verify a JWT access token and return the subject (user id) if valid."""
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=self._algorithm,
                options={"require": ["exp", "sub"]},  # reject tokens without an expiry or subject 
            )
            return int(payload["sub"])
        except (jwt.InvalidTokenError) as exc:
            raise AuthenticationError("Invalid or expired token.") from exc            


class Sha256ResetTokenService(ResetTokenService):
    """The secret is 32 random bytes, so even a fast hash cannot be brute-force."""


    def generate(self) -> str:
        return secrets.token_urlsafe(32)


    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()