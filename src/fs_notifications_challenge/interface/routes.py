from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

# from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import fs_notifications_challenge.infrastructure.models as models
from fs_notifications_challenge.application.create_notification import CreateNotification
from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.application.send_notification import SendNotification
from fs_notifications_challenge.domain.notification import Notification
from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository
from fs_notifications_challenge.interface.dependencies import (
    get_create_notification,
    get_list_notifications,
    get_send_notification,
)
from fs_notifications_challenge.interface.schemas import (
    NotificationCreateRequest,
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


@router.post(
        "",
        response_model=NotificationResponse,
        status_code=status.HTTP_201_CREATED,
)
async def create_notification(
    payload: NotificationCreateRequest,
    use_case: Annotated[CreateNotification, Depends(get_create_notification)],
) -> NotificationResponse:
    notification = await use_case.execute(
        user_id=payload.user_id,
        title=payload.title,
        content=payload.content,
        channel=payload.channel,
        recipient=payload.recipient,
    )
    return NotificationResponse.model_validate(notification)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    use_case: Annotated[ListNotifications, Depends(get_list_notifications)],
) -> NotificationResponse:
    notifications = await use_case.execute()
    for notification in notifications:
        if notification.id == notification_id:
            return NotificationResponse.model_validate(notification)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")


@router.patch(
    "",
    response_model=NotificationResponse, 
    status_code=status.HTTP_201_CREATED,
)
async def send_notification(
    payload: SendNotificationRequest,
    use_case: Annotated[SendNotification, Depends(get_send_notification)],
) -> NotificationResponse:

    notification = await use_case.execute(
        status=payload.status,
        sent_at=payload.sent_at,
    )
    return NotificationResponse.model_validate(notification)