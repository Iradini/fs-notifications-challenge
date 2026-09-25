from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.interface.dependencies import get_list_notifications
from fs_notifications_challenge.interface.templates import templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False, name="home")
@router.get("/notifications", response_class=HTMLResponse, include_in_schema=False, name="posts")
@router.get("/api/notifications", response_class=HTMLResponse, include_in_schema=False, name="posts")
async def home(
    request: Request,
    list_notifications: Annotated[ListNotifications, Depends(get_list_notifications)],
):
    notifications = await list_notifications.execute()
    return templates.TemplateResponse(
        request,
        "home.html",
        {"notifications": notifications, "title": "Home"},
    )


@router.get("/notifications/{notification_id}", include_in_schema=False)
async def notification_page(
    request: Request, 
    notification_id: int,
    list_notifications: Annotated[ListNotifications, Depends(get_list_notifications)],
):
    notifications = await list_notifications.execute()
    for notification in notifications:
        if notification.id ==  notification_id:
            title = notification.title
            return templates.TemplateResponse(
                request,
                "notification.html",
                {"notification": notification, "title": title},
            )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Notification not found",
    )