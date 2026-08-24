import logging
from asyncio import to_thread
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.application.exceptions import UserAlreadyExistsError
from app.application.interfaces import PasswordHasher, UserUnitOfWork
from app.domain.entities import User

logger = logging.getLogger("aml.users")


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    username: str
    email: str
    password: str
    first_name: str | None = None
    last_name: str | None = None
    role: str = "user"


class CreateUserUseCase:
    def __init__(self, unit_of_work: UserUnitOfWork, password_hasher: PasswordHasher):
        self._unit_of_work = unit_of_work
        self._password_hasher = password_hasher

    async def execute(self, command: CreateUserCommand) -> User:
        username = command.username.strip()
        email = command.email.strip().lower()
        if await self._unit_of_work.users.get_by_username(username) is not None:
            raise UserAlreadyExistsError("Username is already registered")
        if await self._unit_of_work.users.get_by_email(email) is not None:
            raise UserAlreadyExistsError("Email is already registered")

        now = datetime.now(UTC)
        user = User(
            id=uuid4(),
            username=username,
            email=email,
            password_hash=await to_thread(self._password_hasher.hash, command.password),
            first_name=command.first_name,
            last_name=command.last_name,
            is_active=True,
            is_verified=False,
            role=command.role,
            created_at=now,
            updated_at=now,
        )
        saved_user = await self._unit_of_work.users.add(user)
        await self._unit_of_work.commit()

        logger.info(
            "User created",
            extra={
                "event": {
                    "action": "user.create",
                    "dataset": "aml.users",
                    "outcome": "success",
                },
                "resource": {"id": str(saved_user.id), "type": "user"},
            },
        )
        return saved_user