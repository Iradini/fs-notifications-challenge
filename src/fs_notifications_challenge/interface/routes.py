from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from fs_notifications_challenge.application.create_notification import CreateNotification
from fs_notifications_challenge.application.delete_notification import DeleteNotification
from fs_notifications_challenge.application.get_notification import GetNotification
from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.application.update_notification import UpdateNotification
from fs_notifications_challenge.interface.dependencies import (
    get_create_notification,
    get_delete_notification,
    get_get_notification,
    get_list_notifications,
    get_update_notification,
)
from fs_notifications_challenge.interface.schemas import (
    NotificationCreateRequest,
    NotificationResponse,
    NotificationUpdateRequest,
)

router = APIRouter()

@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    use_case: Annotated[ListNotifications, Depends(get_list_notifications)],
) -> list[NotificationResponse]:
    notifications = await use_case.execute()    
    return [NotificationResponse.model_validate(n) for n in notifications]


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    payload: NotificationCreateRequest,
    use_case: Annotated[CreateNotification, Depends(get_create_notification)],
) -> NotificationResponse:
    notification = await use_case.execute(
        user_id=payload.user_id,
        title=payload.title,
        content=payload.content,
        channel=payload.channel,
        recipient=payload.recipient.to_domain(),
    )
    return NotificationResponse.from_domain(notification)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    use_case: Annotated[ListNotifications, Depends(get_get_notification)],
) -> NotificationResponse:
    notification = await use_case.execute(notification_id)
    return NotificationResponse.from_domain(notification)


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: int,
    payload: NotificationUpdateRequest,
    use_case: Annotated[UpdateNotification, Depends(get_update_notification)],
) -> NotificationResponse:
    notification = await use_case.execute(
        notification_id,
        title=payload.title,
        content=payload.content,
        channel=payload.channel,
        recipient=payload.recipient.to_domain() if payload.recipient else None,
    )
    return NotificationResponse.from_domain(notification)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    use_case: Annotated[DeleteNotification, Depends(get_delete_notification)],
) -> Response:
    await use_case.execute(notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)