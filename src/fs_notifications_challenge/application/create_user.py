from dataclasses import dataclass

from fs_notifications_challenge.application.ports import UserRepository
from fs_notifications_challenge.domain.errors import ConflictError
from fs_notifications_challenge.domain.user import User


@dataclass
class CreateUser:
    repository: UserRepository

    async def execute(self, email: str) -> User:
        if await self.repository.get_by_email(email) is not None:
            raise ConflictError(f"A user with {email} already exists.")
        return await self.repository.add(User(email=email))