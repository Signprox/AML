from typing import Protocol

from app.domain.entities import AuditEvent


class AuditRepository(Protocol):
    async def add(self, event: AuditEvent) -> AuditEvent: ...
