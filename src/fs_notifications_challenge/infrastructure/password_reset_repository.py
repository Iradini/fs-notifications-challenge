from datetime import UTC

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from fs_notifications_challenge.application.ports import PasswordResetTokenRepository
from fs_notifications_challenge.domain.password_reset import PasswordResetToken
from fs_notifications_challenge.infrastructure.models import PasswordResetTokenModel


class SQLAlchemyPasswordResetTokenRepository(PasswordResetTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def add(self, token: PasswordResetToken) -> PasswordResetToken:
        row = PasswordResetTokenModel(
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            created_at=token.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        token.id = row.id
        return token


    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self._session.execute(
            select(PasswordResetTokenModel).where(PasswordResetTokenModel.token_hash == token_hash),
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None


    async def delete_for_user(self, user_id: int) -> None:
        await self._session.execute(
            delete(PasswordResetTokenModel).where(PasswordResetTokenModel.user_id == user_id),
        )


    @staticmethod
    def _to_domain(row: PasswordResetTokenModel) -> PasswordResetToken:
        # SQLite hands datetimes back WITHOUT their timezone. Everything we store is UTC,
        # so say so: comparing a naive datetime with an aware one raises TypeError
        return PasswordResetToken(
            id=row.id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            expires_at=row.expires_at.replace(tzinfo=UTC) if row.expires_at.tzinfo is None else row.expires_at,
            created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at,
        )  
