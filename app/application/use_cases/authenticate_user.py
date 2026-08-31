from uuid import UUID

from app.application.exceptions import AuthenticationError, NotFoundError
from app.application.interfaces import UserRepository
from app.domain.entities import User


class AuthenticateUserUseCase:
    def __init__(self, repository: UserRepository):
        self._repository = repository

    async def execute(self, user_id: UUID) -> User:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if not user.is_active:
            raise AuthenticationError("User account is inactive")
        return user
