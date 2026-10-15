from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from fs_notifications_challenge.application.log_in import LogIn
from fs_notifications_challenge.interface.dependencies import get_login_in
from fs_notifications_challenge.interface.auth import CurrentUser
from fs_notifications_challenge.interface.schemas import Token, UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def read_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.from_domain(current_user)


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    use_case: Annotated[LogIn, Depends(get_login_in)],
) -> Token:
    access_token = await use_case.execute(email=form_data.username, password=form_data.password)
    return Token(access_token=access_token)