from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.application.send_notification import SendNotification
from fs_notifications_challenge.domain.notification import DomainError, Notification
from fs_notifications_challenge.infrastructure.database import get_db
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository
from fs_notifications_challenge.interface.dependencies import (
    get_list_notifications,
    get_send_notification,
)
from fs_notifications_challenge.interface.schemas import (
    NotificationResponse,
    SendNotificationRequest,
)

router = APIRouter()

@router.get("", response_model=list[NotificationResponse])
async def get_notifications(
    use_case: Annotated[ListNotifications, Depends(get_list_notifications)],
) -> list[NotificationResponse]:
    notifications = await use_case.execute()
    return [NotificationResponse.model_validate(n) for n in notifications]


@router.get("/{notification_id}")
async def get_notification(
    notification_id: int,
    use_case: Annotated[ListNotifications, Depends(get_list_notifications)],
) -> Notification:
    notifications = await use_case.execute()
    for notification in notifications:
        if notification.id == notification_id:
            return notification
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")


@router.post(
    "",
    response_model=NotificationResponse, 
    status_code=status.HTTP_201_CREATED,
)
async def send_notification(
    payload: SendNotificationRequest,
    use_case: Annotated[SendNotification, Depends(get_send_notification)],
) -> NotificationResponse:

    notification = await use_case.execute(
        sender_id=payload.sender_id,
        recipient_id=payload.recipient_id,
        title=payload.title,
        message=payload.message,
    )
    return NotificationResponse.model_validate(notification)