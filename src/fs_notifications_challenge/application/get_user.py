from dataclasses import dataclass

from fs_notifications_challenge.application.ports import UserRepository
from fs_notifications_challenge.domain.errors import NotFoundError
from fs_notifications_challenge.domain.user import User


@dataclass
class GetUser:
    repository: UserRepository

    async def execute(self, user_id: int) -> User:
        user = await self.repository.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        return User
