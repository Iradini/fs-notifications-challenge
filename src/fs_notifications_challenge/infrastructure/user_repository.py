from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.ports import UserRepository
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import ConcurrentUpdateError, ConflictError, NotFoundError
from fs_notifications_challenge.domain.user import User, UserProfile
from fs_notifications_challenge.infrastructure.models import (
    DeliveryAttemptModel,
    NotificationModel,
    OutboxMessageModel,
    UserModel, 
    UserProfileModel,
)


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def add(self, user: User) -> User:
        row = UserModel(email=user.email, password_hash=user.password_hash)
        self._session.add(row)
        await self._session.flush()
        user.id = row.id
        return user


    async def get(self, user_id: int) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return self._to_domain(row) if row is not None else None


    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(func.lower(UserModel.email) == email.lower()))
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None


    async def update(self, user: User) -> User:
        """Persist the user's email and profile. The profile row is created,
        updated or removed to match `user.profile`."""
        row = await self._session.get(UserModel, user.id)
        if row is None:
            raise NotFoundError(f"User {user.id} not found.")
                
        row.email = user.email
        row.password_hash = user.password_hash
        if user.profile is None:
            row.profile = None          # delete-orphan removes the row
        else:
            if row.profile is None:
                row.profile = UserProfileModel()
            row.profile.email = user.profile.contact.email
            row.profile.phone = user.profile.contact.phone
            row.profile.token = user.profile.contact.token

        try:
            await self._session.flush()
        except IntegrityError as exc:
            # The use case already checked, but two requests can raice for the same
            # email; the UNIQUE constraint is the one that never loses.
            raise ConflictError(f"A user with {user.email} already exists.")
        if user.profile is not None:
            user.profile.id = row.profile.id
        return user


    async def delete(self, user: User) -> None:
        """Hard delete. Foreign keys are enforced, so children go first: delivery
        attempts and outbox rows hang from notifications, notifications from the
        user. The profile goes with the user(ORM cascade)."""
        row = await self._session.get(UserModel, user.id)
        if row is None:
            return
        mine = select(NotificationModel.id).where(NotificationModel.user_id == user.id)
        try:
            await self._session.execute(
                delete(DeliveryAttemptModel).where(DeliveryAttemptModel.notification_id.in_(mine)),
            )
            await self._session.execute(
                delete(OutboxMessageModel).where(OutboxMessageModel.notification_id.in_(mine)),
            )
            await self._session.execute(delete(NotificationModel).where(NotificationModel.user_id == user.id))
            await self._session.delete(row)
            await self._session.flush()
        except IntegrityError as exc:
            # The worker wrote a delivery attempt for one of these notifications
            # between our statements. Nothing was deleted (get_db rolls back): retry.
            raise ConcurrentUpdateError("The account changed while it was being deleted. Try again.") from exc


    @staticmethod
    def _to_domain(row: UserModel) -> User:
        profile = None
        if row.profile is not None:
            profile = UserProfile(
                id=row.profile.id,
                user_id=row.id,
                contact=ContactInfo(email=row.profile.email, phone=row.profile.phone, token=row.profile.token),
            )
        return User(id=row.id, email=row.email, password_hash=row.password_hash, profile=profile)