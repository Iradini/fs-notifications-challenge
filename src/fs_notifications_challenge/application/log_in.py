from dataclasses import dataclass

from fs_notifications_challenge.application.ports import PasswordHasher, TokenService, UserRepository
from fs_notifications_challenge.domain.errors import AuthenticationError


@dataclass
class LogIn:
    users: UserRepository
    hasher: PasswordHasher
    tokens: TokenService


    async def execute(self, email: str, password: str) -> str:
        user = await self.users.get_by_email(email)
        # Same error for "no such email" and "worng password", so the login form
        # can't be used to find out which emails have accounts.
        if user is None or not user.password_hash or not self.hasher.verify_password(password, user.password_hash):
            raise AuthenticationError("Incorrect email or password.")
        return self.tokens.issue(user.id)