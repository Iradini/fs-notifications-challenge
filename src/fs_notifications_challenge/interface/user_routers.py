from typing import Annotated

from fastapi import APIRouter, Depends, status

from fs_notifications_challenge.application.create_user import CreateUser
from fs_notifications_challenge.application.get_user import GetUser
from fs_notifications_challenge.application.save_user_profile import SaveUserProfile
from fs_notifications_challenge.interface.dependencies import (
    get_create_user,
    get_get_user,
    get_save_user_profile,
)
from fs_notifications_challenge.interface.schemas import (
    ProfileInfo,
    UserCreateRequest,
    UserResponse,
)

router = APIRouter()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    use_case: Annotated[CreateUser, Depends(get_create_user)],
) -> UserResponse:
    user = await use_case.execute(payload.email)
    return UserResponse.from_domain(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int, 
    use_case: Annotated[GetUser, Depends(get_get_user)],
) -> UserResponse:
    user = await use_case.execute(user_id)
    return UserResponse.from_domain(user)


@router.put("/{user_id}/profile", response_model=UserResponse)
async def save_user_profile(
    user_id: int,
    payload: ProfileInfo,
    use_case: Annotated[SaveUserProfile, Depends(get_save_user_profile)],
) -> UserResponse:
    user_profile = await use_case.execute(user_id, payload.to_domain())
    return UserResponse.from_domain(user_profile) 