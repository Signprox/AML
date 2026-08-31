import logging
from asyncio import to_thread
from dataclasses import dataclass

from app.application.exceptions import UserAlreadyExistsError, ValidationError
from app.application.interfaces import AuditRepository, PasswordHasher, UserUnitOfWork
from app.domain.entities import User
from app.domain.value_objects import InvalidEmailError, InvalidUsernameError
from app.infrastructure.repositories.sql_audit_repository import record_audit

logger = logging.getLogger("aml.users")


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    username: str
    email: str
    password: str
    first_name: str | None = None
    last_name: str | None = None


def validate_password(password: str) -> None:
    import re

    if len(password) < 8 or len(password) > 128:
        raise ValidationError("Password must be between 8 and 128 characters")
    if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).+$", password):
        raise ValidationError(
            "Password must contain uppercase, lowercase, digit, and special character"
        )


class CreateUserUseCase:
    def __init__(
        self,
        unit_of_work: UserUnitOfWork,
        password_hasher: PasswordHasher,
        audit_repository: AuditRepository | None = None,
    ):
        self._unit_of_work = unit_of_work
        self._password_hasher = password_hasher
        self._audit_repository = audit_repository

    async def execute(self, command: CreateUserCommand) -> User:
        validate_password(command.password)
        try:
            user = User.create(
                username=command.username,
                email=command.email,
                password_hash=await to_thread(
                    self._password_hasher.hash, command.password
                ),
                first_name=command.first_name,
                last_name=command.last_name,
                role="user",
            )
        except (InvalidUsernameError, InvalidEmailError) as exc:
            raise ValidationError(str(exc)) from exc

        if await self._unit_of_work.users.get_by_username(user.username) is not None:
            raise UserAlreadyExistsError("Username is already registered")
        if await self._unit_of_work.users.get_by_email(user.email) is not None:
            raise UserAlreadyExistsError("Email is already registered")

        saved_user = await self._unit_of_work.users.add(user)
        await self._unit_of_work.commit()

        if self._audit_repository is not None:
            await record_audit(
                self._audit_repository,
                action="user.create",
                resource_type="user",
                resource_id=str(saved_user.id),
                outcome="success",
                actor_id=saved_user.id,
            )

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
