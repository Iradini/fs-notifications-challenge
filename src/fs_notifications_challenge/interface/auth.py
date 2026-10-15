from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from fs_notifications_challenge.application.ports import TokenService
from fs_notifications_challenge.domain.errors import AuthenticationError
from fs_notifications_challenge.domain.user import User
from fs_notifications_challenge.infrastructure.user_repository import SQLAlchemyUserRepository
from fs_notifications_challenge.interface.dependencies import Db, get_token_service


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")


async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        tokens: Annotated[TokenService, Depends(get_token_service)],
        db: Db,
) -> User:
    user_id = tokens.verify_access_token(token) 
    user = await SQLAlchemyUserRepository(db).get(user_id)
    if user is None:
        raise AuthenticationError("User no longer exists.")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]
