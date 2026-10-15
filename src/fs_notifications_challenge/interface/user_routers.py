from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from fs_notifications_challenge.application.change_password import ChangePassword
from fs_notifications_challenge.application.create_user import CreateUser
from fs_notifications_challenge.application.delete_user import DeleteUser
from fs_notifications_challenge.application.delete_user_profile import DeleteUserProfile
from fs_notifications_challenge.application.get_user import GetUser
from fs_notifications_challenge.application.update_user import UpdateUser
from fs_notifications_challenge.domain.errors import NotFoundError
from fs_notifications_challenge.interface.auth import CurrentUser
from fs_notifications_challenge.interface.dependencies import (
    get_change_password,
    get_create_user,
    get_delete_user,
    get_delete_user_profile,
    get_get_user,
    get_update_user,
)
from fs_notifications_challenge.interface.schemas import (
    AccountDeleteRequest,
    PasswordChangeRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter()


def _only_yourself(requested_id: int, current_id: int) -> None:
    if requested_id != current_id:
        raise NotFoundError(f"User {requested_id} not found.")


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    use_case: Annotated[CreateUser, Depends(get_create_user)],
) -> UserResponse:
    user = await use_case.execute(payload.email, payload.password)
    return UserResponse.from_domain(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: CurrentUser, 
    use_case: Annotated[GetUser, Depends(get_get_user)],
) -> UserResponse:
    _only_yourself(user_id, current_user.id)
    user = await use_case.execute(user_id)
    return UserResponse.from_domain(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: CurrentUser,
    use_case: Annotated[UpdateUser, Depends(get_update_user)],
) -> UserResponse:
    _only_yourself(user_id, current_user.id)
    contact = payload.profile.to_domain() if payload.profile is not None else None
    user = await use_case.execute(user_id, email=payload.email, contact=contact)
    return UserResponse.from_domain(user)


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    user_id: int,
    payload: PasswordChangeRequest,
    current_user: CurrentUser,
    use_case: Annotated[ChangePassword, Depends(get_change_password)],
) -> Response:
    _only_yourself(user_id, current_user.id)
    await use_case.execute(user_id, payload.current_password, payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{user_id}/profile", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_profile( 
    user_id: int,
    current_user: CurrentUser,
    use_case: Annotated[DeleteUserProfile, Depends(get_delete_user_profile)],   
) -> Response: 
    _only_yourself(user_id, current_user.id)
    await use_case.execute(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    payload: AccountDeleteRequest,
    current_user: CurrentUser,
    user_case: Annotated[DeleteUser, Depends(get_delete_user)],
) -> Response:
    _only_yourself(user_id, current_user.id)
    await user_case.execute(user_id, payload.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)