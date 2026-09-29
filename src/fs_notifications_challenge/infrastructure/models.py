from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fs_notifications_challenge.domain.notification import Status
from fs_notifications_challenge.infrastructure.database import Base


class UserModel(Base):
    __tablename__= "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    notifications: Mapped[list[NotificationModel]] = relationship(back_populates="sender")


# class UserProfileModel(UserModel):
#     __tablename__= "profiles"
#     phone: Mapped[str] = mapped_column(String(120), nullable=False)


class NotificationModel(Base):
    __tablename__= "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=Status.CREATED.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)

    sender: Mapped[UserModel] = relationship(back_populates="notifications")
