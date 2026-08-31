from uuid import UUID

from app.application.exceptions import NotFoundError
from app.application.interfaces import AuditRepository, UserRepository
from app.domain.entities import User
from app.infrastructure.repositories.sql_audit_repository import record_audit


class GetUserByNameUseCase:
    def __init__(
        self,
        repository: UserRepository,
        audit_repository: AuditRepository | None = None,
    ):
        self._repository = repository
        self._audit_repository = audit_repository

    async def execute(self, user_name: str, *, actor_id: UUID | None = None) -> User:
        user = await self._repository.get_by_username(user_name)
        if user is None:
            raise NotFoundError("User not found")

        if self._audit_repository is not None:
            await record_audit(
                self._audit_repository,
                action="user.read",
                resource_type="user",
                resource_id=str(user.id),
                outcome="success",
                actor_id=actor_id,
            )

        return user
