from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from fs_notifications_challenge.application.delete_notification import DeleteNotification
from fs_notifications_challenge.application.get_notification import GetNotification
from fs_notifications_challenge.application.list_notification import ListNotifications
from fs_notifications_challenge.interface.dependencies import (
    get_delete_notification,
    get_get_notification,
    get_list_notifications,    
)
from fs_notifications_challenge.interface.templates import templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False, name="home")
@router.get("/notifications", response_class=HTMLResponse, include_in_schema=False, name="posts")
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
    get_notification: Annotated[GetNotification, Depends(get_get_notification)],
):
    notification = await get_notification.execute(notification_id)
    return templates.TemplateResponse(
        request,
        "notification.html",
        {"notification": notification, "title": notification.title},
    )


@router.post("/notifications/{notification_id}/delete", include_in_schema=False, name="delete_notification_page")
async def delete_notification_page(
    notification_id: int,
    delete_notification: Annotated[DeleteNotification, Depends(get_delete_notification)],
):
    await delete_notification.execute(notification_id)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)