# from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.orm import Session

# from fs_notifications_challenge.application.send_notification import SendNotification
# from fs_notifications_challenge.domain.notification import DomainError
# from fs_notifications_challenge.infrastructure.database import get_db
# from fs_notifications_challenge.infrastructure.repository import SQLAlchemyNotificationRepository
# from fs_notifications_challenge.interface.schemas import (
#     NotificationResponse,
#     SendNotificationRequest,
# )

router = APIRouter()

templates = Jinja2Templates(directory="templates")

notifications: list[dict] = [
    {
        "id": 1,
        "sender_id": 1,
        "recipient_id": 2,
        "title": "Notification 1",
        "content": "This framework is really easy to use and super fast.",
        "created_at": "April 20, 2025",
    },
    {
        "id": 2,
        "sender_id": 2,
        "recipient_id": 3,
        "title": "Notification 2",
        "content": "Python is a great language for web development, and FastAPI makes it even better.",
        "created_at": "April 21, 2025",
    },
]


@router.get("/", response_class=HTMLResponse, include_in_schema=False, name="home")
@router.get("/notifications", response_class=HTMLResponse, include_in_schema=False, name="posts")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "home.html",
        {"notifications": notifications, "title": "Home"},
    )


@router.get("")
def get_posts():
    return notifications


# def get_send_notification(db: Annotated[Session, Depends(get_db)]) -> SendNotification:
#     repository = SQLAlchemyNotificationRepository(db)
#     return SendNotification(repository=repository)


# @router.post(
#     "",
#     response_model=NotificationResponse, 
#     status_code=status.HTTP_201_CREATED,
# )
# def send_notification(
#     payload: SendNotificationRequest,
#     use_case: Annotated[SendNotification, Depends(get_send_notification)],
# ) -> NotificationResponse:
#     try:
#         notification = use_case.execute(
#             sender_id=payload.sender_id,
#             recipient_id=payload.recipient_id,
#             message=payload.message,
#         )
#     except DomainError as err:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail=str(err),
#         ) from err
#     return NotificationResponse.model_validate(notification)