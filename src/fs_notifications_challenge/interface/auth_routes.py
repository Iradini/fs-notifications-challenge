from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from fs_notifications_challenge.application.log_in import LogIn
from fs_notifications_challenge.application.request_password_reset import RequestPasswordReset
from fs_notifications_challenge.application.reset_password import ResetPassword
from fs_notifications_challenge.interface.dependencies import (
    get_login_in,
    get_request_password_reset,
    get_reset_password,    
)
from fs_notifications_challenge.interface.auth import CurrentUser
from fs_notifications_challenge.interface.schemas import (
    ForgotPasswordRequest,
    MessageResponse,
    PasswordResetRequest,
    Token, 
    UserResponse,
)

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


@router.post("/forgot-password", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotPasswordRequest,
    use_case: Annotated[RequestPasswordReset, Depends(get_request_password_reset)],
) -> MessageResponse:
    await use_case.execute(payload.email)
    # The same answer whether or not the email has an account
    return MessageResponse(
        message="If an account exists with this email, you will receive password reset instructions.",
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: PasswordResetRequest,
    use_case: Annotated[ResetPassword, Depends(get_reset_password)],
) -> MessageResponse:
    await use_case.execute(payload.token, payload.new_password)
    return MessageResponse(message="Password reset successfully. You can now log in with your new password.")
