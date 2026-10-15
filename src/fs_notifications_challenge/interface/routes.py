from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Response, status

from fs_notifications_challenge.application.create_notification import CreateNotification
from fs_notifications_challenge.application.delete_notification import DeleteNotification
from fs_notifications_challenge.application.get_notification import GetNotification
from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.application.update_notification import UpdateNotification
from fs_notifications_challenge.config import settings
from fs_notifications_challenge.interface.auth import CurrentUser
from fs_notifications_challenge.interface.dependencies import (
    get_create_notification,
    get_delete_notification,
    get_get_notification,
    get_list_notifications,
    get_update_notification,
)
from fs_notifications_challenge.interface.schemas import (
    CHANNEL_DISCRIMINATOR,
    NotificationCreateRequest,
    NotificationResponse,
    NotificationUpdateRequest,
    PaginatedNotificationsResponse,
)

router = APIRouter()

MAX_PAGE_SIZE = 100


@router.get("", response_model=PaginatedNotificationsResponse)
async def list_notifications(
    current_user: CurrentUser,
    use_case: Annotated[ListNotifications, Depends(get_list_notifications)],
    skip: Annotated[int, Query(ge=0, description="How many notifications to skip.")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="Page size."),
    ] = settings.notifications_per_page,
) -> PaginatedNotificationsResponse:
    page = await use_case.execute(current_user.id, skip=skip, limit=limit)    
    return PaginatedNotificationsResponse.from_page(page)


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    current_user: CurrentUser,
    payload: Annotated[
        NotificationCreateRequest, 
        Body(discriminator=CHANNEL_DISCRIMINATOR),
    ],
    use_case: Annotated[CreateNotification, Depends(get_create_notification)],
) -> NotificationResponse:
    notification = await use_case.execute(
        user_id=current_user.id,
        title=payload.title,
        content=payload.content,
        channel=payload.channel,
        recipient=payload.recipient.to_domain(),
    )
    return NotificationResponse.from_domain(notification)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    current_user: CurrentUser,
    use_case: Annotated[GetNotification, Depends(get_get_notification)],
) -> NotificationResponse:
    notification = await use_case.execute(notification_id, current_user.id)
    return NotificationResponse.from_domain(notification)


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: int,
    payload: NotificationUpdateRequest,
    current_user: CurrentUser,
    use_case: Annotated[UpdateNotification, Depends(get_update_notification)],
) -> NotificationResponse:
    notification = await use_case.execute(
        notification_id,
        current_user.id,
        title=payload.title,
        content=payload.content,
        channel=payload.channel,
        recipient=payload.recipient.to_domain() if payload.recipient else None,
    )
    return NotificationResponse.from_domain(notification)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    current_user: CurrentUser,
    use_case: Annotated[DeleteNotification, Depends(get_delete_notification)],
) -> Response:
    await use_case.execute(notification_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)