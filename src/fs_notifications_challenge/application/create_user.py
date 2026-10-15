from dataclasses import dataclass

from fs_notifications_challenge.application.ports import UserRepository, PasswordHasher
from fs_notifications_challenge.domain.errors import ConflictError
from fs_notifications_challenge.domain.user import User


@dataclass
class CreateUser:
    repository: UserRepository
    hasher: PasswordHasher

    async def execute(self, email: str, password: str) -> User:
        if await self.repository.get_by_email(email) is not None:
            raise ConflictError(f"A user with {email} already exists.")
        user = User(email=email, password_hash=self.hasher.hash_password(password))
        return await self.repository.add(user)