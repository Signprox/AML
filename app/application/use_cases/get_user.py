from uuid import UUID

from app.application.exceptions import NotFoundError
from app.application.interfaces import AuditRepository, UserRepository
from app.domain.entities import User


class GetUserUseCase:
    def __init__(
        self,
        repository: UserRepository,
        audit_repository: AuditRepository | None = None,
    ):
        self._repository = repository
        self._audit_repository = audit_repository

    async def execute(self, user_id: UUID, *, actor_id: UUID | None = None) -> User:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        if self._audit_repository is not None:
            from app.infrastructure.repositories.sql_audit_repository import record_audit

            await record_audit(
                self._audit_repository,
                action="user.read",
                resource_type="user",
                resource_id=str(user.id),
                outcome="success",
                actor_id=actor_id,
            )

        return user
