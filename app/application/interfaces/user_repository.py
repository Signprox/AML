from typing import Protocol
from uuid import UUID

from app.domain.entities import User


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_username(self, username: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def add(self, user: User) -> User: ...

    async def update(self, user: User) -> User: ...


class UserUnitOfWork(Protocol):
    users: UserRepository

    async def commit(self) -> None: ...
