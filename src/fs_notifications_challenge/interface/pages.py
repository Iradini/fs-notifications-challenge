"""HTML pages. They are empty shells: they never read the database.

The browser holds the login token (see static/js/auth.js), so each page's script
fetches its own data from /api/... with `Authorization: Bearer ...`. The server
can't tell who is asking when it rendes HTML, so nothing private is put in it.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from fs_notifications_challenge.interface.templates import templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False, name="home")
@router.get("/notifications", response_class=HTMLResponse, include_in_schema=False, name="posts")
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"title": "Home"})


@router.get("/notifications/{notification_id}", include_in_schema=False, name="notification_page")
async def notification_page(request: Request, notification_id: int):
    return templates.TemplateResponse(
        request,
        "notification.html",
        {"notification_id": notification_id, "title": "Notification"},
    )


@router.get("/account", response_class=HTMLResponse, include_in_schema=False, name="account_page")
async def account_page(request: Request):
    return templates.TemplateResponse(request, "account.html", {"title": "Account"})


@router.get("/login", response_class=HTMLResponse, include_in_schema=False, name="login_page")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@router.get("/register", response_class=HTMLResponse, include_in_schema=False, name="register_page")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})