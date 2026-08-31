import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from time import perf_counter_ns
from typing import Any

from sqlalchemy import Executable, text
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("aml.database")


class DatabaseHelper:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def execute(
        self,
        statement: Executable,
        parameters: Mapping[str, Any] | None = None,
    ) -> Result[Any]:

        return await self._execute(
            statement,
            parameters,
            action="database.execute",
        )

    async def execute_raw(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> Result[Any]:

        if not query.strip():
            raise ValueError("Raw SQL query must not be empty")
        return await self._execute(
            text(query),
            parameters,
            action="database.execute_raw",
        )

    async def flush(self, objects: Sequence[Any] | None = None) -> None:
        """Flush pending ORM changes without committing the transaction."""
        await self._run_session_operation(
            "database.flush",
            lambda: self._session.flush(objects),
        )

    async def update(self, instance: Any) -> Any:
        """Merge ORM changes and flush without committing the transaction."""
        started_at = perf_counter_ns()
        try:
            merged = await self._session.merge(instance)
            await self._session.flush()
        except Exception as exc:
            logger.error(
                "Database session operation failed",
                extra=self._log_fields(
                    action="database.update",
                    outcome="failure",
                    started_at=started_at,
                    error_type=type(exc).__name__,
                ),
            )
            raise
        logger.info(
            "Database session operation completed",
            extra=self._log_fields(
                action="database.update",
                outcome="success",
                started_at=started_at,
            ),
        )
        return merged

    async def commit(self) -> None:
        """Commit the current transaction with sanitized telemetry."""
        await self._run_session_operation(
            "database.commit",
            self._session.commit,
        )

    async def rollback(self) -> None:
        """Roll back the current transaction with sanitized telemetry."""
        await self._run_session_operation(
            "database.rollback",
            self._session.rollback,
        )

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["DatabaseHelper"]:
        """Commit all operations in the block, or roll them back on failure."""
        started_at = perf_counter_ns()
        try:
            async with self._session.begin():
                yield self
        except Exception as exc:
            logger.error(
                "Database transaction failed",
                extra=self._log_fields(
                    action="database.transaction",
                    outcome="failure",
                    started_at=started_at,
                    error_type=type(exc).__name__,
                ),
            )
            raise
        logger.info(
            "Database transaction committed",
            extra=self._log_fields(
                action="database.transaction",
                outcome="success",
                started_at=started_at,
            ),
        )

    async def _execute(
        self,
        statement: Executable,
        parameters: Mapping[str, Any] | None,
        *,
        action: str,
    ) -> Result[Any]:
        started_at = perf_counter_ns()
        try:
            result = await self._session.execute(statement, parameters)
        except Exception as exc:
            logger.error(
                "Database operation failed",
                extra=self._log_fields(
                    action=action,
                    outcome="failure",
                    started_at=started_at,
                    error_type=type(exc).__name__,
                ),
            )
            raise
        logger.info(
            "Database operation completed",
            extra=self._log_fields(
                action=action,
                outcome="success",
                started_at=started_at,
            ),
        )
        return result

    async def _run_session_operation(
        self,
        action: str,
        operation: Callable[[], Awaitable[None]],
    ) -> None:
        started_at = perf_counter_ns()
        try:
            await operation()
        except Exception as exc:
            logger.error(
                "Database session operation failed",
                extra=self._log_fields(
                    action=action,
                    outcome="failure",
                    started_at=started_at,
                    error_type=type(exc).__name__,
                ),
            )
            raise
        logger.info(
            "Database session operation completed",
            extra=self._log_fields(
                action=action,
                outcome="success",
                started_at=started_at,
            ),
        )

    @staticmethod
    def _log_fields(
        *,
        action: str,
        outcome: str,
        started_at: int,
        error_type: str | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "event": {
                "action": action,
                "dataset": "aml.database",
                "duration": perf_counter_ns() - started_at,
                "outcome": outcome,
            }
        }
        if error_type is not None:
            fields["error"] = {"type": error_type}
        return fields
