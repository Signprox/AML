from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces import AuditRepository
from app.domain.entities import AuditEvent
from app.infrastructure.database import DatabaseHelper
from app.infrastructure.database.models import AuditEventModel


class SqlAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._database = DatabaseHelper(session)

    async def add(self, event: AuditEvent) -> AuditEvent:
        model = AuditEventModel(
            id=event.id,
            actor_id=event.actor_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            outcome=event.outcome,
            details=event.details,
            created_at=event.created_at,
        )
        self._session.add(model)
        await self._database.flush()
        return event


def create_audit_event(
    *,
    action: str,
    resource_type: str,
    outcome: str,
    actor_id: UUID | None = None,
    resource_id: str | None = None,
    details: dict[str, str] | None = None,
) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        details=details,
        created_at=datetime.now(UTC),
    )


async def record_audit(
    repository: AuditRepository,
    *,
    action: str,
    resource_type: str,
    outcome: str,
    actor_id: UUID | None = None,
    resource_id: str | None = None,
    details: dict[str, str] | None = None,
) -> None:
    await repository.add(
        create_audit_event(
            action=action,
            resource_type=resource_type,
            outcome=outcome,
            actor_id=actor_id,
            resource_id=resource_id,
            details=details,
        )
    )
