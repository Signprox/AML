import logging
from asyncio import to_thread
from dataclasses import dataclass
from uuid import UUID

from app.application.exceptions import AuthenticationError
from app.application.interfaces import AuditRepository, PasswordHasher, TokenService, UserRepository
from app.infrastructure.repositories.sql_audit_repository import record_audit

logger = logging.getLogger("aml.users")


@dataclass(frozen=True, slots=True)
class LoginCommand:
    username: str
    password: str


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    token_type: str = "bearer"


class LoginUseCase:
    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        audit_repository: AuditRepository | None = None,
    ):
        self._repository = repository
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._audit_repository = audit_repository

    async def execute(self, command: LoginCommand) -> LoginResult:
        username = command.username.strip()
        user = await self._repository.get_by_username(username)
        if user is None or not user.is_active:
            await self._record_failed_login(username)
            raise AuthenticationError("Invalid username or password")

        valid = await to_thread(
            self._password_hasher.verify, command.password, user.password_hash
        )
        if not valid:
            await self._record_failed_login(username, user.id)
            raise AuthenticationError("Invalid username or password")

        token = self._token_service.create_token(
            str(user.id),
            claims={"username": user.username, "role": user.role},
        )

        if self._audit_repository is not None:
            await record_audit(
                self._audit_repository,
                action="user.login",
                resource_type="user",
                resource_id=str(user.id),
                outcome="success",
                actor_id=user.id,
            )

        logger.info(
            "User logged in",
            extra={
                "event": {
                    "action": "user.login",
                    "dataset": "aml.users",
                    "outcome": "success",
                },
                "resource": {"id": str(user.id), "type": "user"},
            },
        )
        return LoginResult(access_token=token)

    async def _record_failed_login(
        self, username: str, actor_id: UUID | None = None
    ) -> None:
        if self._audit_repository is None:
            return
        await record_audit(
            self._audit_repository,
            action="user.login.failed",
            resource_type="user",
            resource_id=str(actor_id) if actor_id else None,
            outcome="failure",
            actor_id=actor_id,
            details={"username": username},
        )
