from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.ports import UserRepository
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.user import User, UserProfile
from fs_notifications_challenge.infrastructure.models import UserModel, UserProfileModel


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def add(self, user: User) -> User:
        row = UserModel(email=user.email)
        self._session.add(row)
        await self._session.flush()
        user.id = row.id
        return user


    async def get(self, user_id: int) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return self._to_domain(row) if row is not None else None


    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None


    async def save_profile(self, profile: UserProfile) -> UserProfile:
        result = await self._session.execute(
            select(UserProfileModel).where(UserProfileModel.user_id == profile.user_id),
        )
        row = result.scalar_one_or_none() or UserProfileModel(user_id=profile.user_id)
        row.email = profile.contact.email
        row.phone = profile.contact.phone
        row.token = profile.contact.token
        self._session.add(row)
        await self._session.flush()
        profile.id = row.id
        return profile


    @staticmethod
    def _to_domain(row: UserModel) -> User:
        profile = None
        if row.profile is not None:
            profile = UserProfile(
                id=row.profile.id,
                user_id=row.id,
                contact=ContactInfo(email=row.profile.email, phone=row.profile.phone, token=row.profile.token),
            )
        return User(id=row.id, email=row.email, profile=profile)