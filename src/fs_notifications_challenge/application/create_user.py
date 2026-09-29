from dataclasses import dataclass

from fs_notifications_challenge.application.ports import UserRepository
from fs_notifications_challenge.domain.user_profile import UserProfile


@dataclass
class CreateUser:
    repository: UserRepository

    async def execute(
            self, 
            email: str,
            phone: str,
    ) -> UserProfile:
        user_profile = UserProfile(
            email=email,
            phone=phone,
        )
        return await self.repository.create(user_profile)