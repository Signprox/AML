from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    details: dict[str, str] | None
    created_at: datetime
