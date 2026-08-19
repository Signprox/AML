import logging
from collections.abc import AsyncIterator
from threading import Lock
from time import perf_counter_ns

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


logger = logging.getLogger("aml.database")
_configuration_lock = Lock()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _event(action: str, outcome: str, duration_ns: int | None = None) -> dict:
    event: dict[str, str | int] = {
        "action": action,
        "dataset": "aml.database",
        "outcome": outcome,
    }
    if duration_ns is not None:
        event["duration"] = duration_ns
    return {"event": event}


def configure_database(settings: Settings) -> None:
    global _engine, _session_factory

    with _configuration_lock:
        if _engine is not None:
            return

        started_at = perf_counter_ns()
        try:
            engine = create_async_engine(
                settings.database_url,
                pool_pre_ping=True,
                echo=False,
            )
            session_factory = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        except Exception as exc:
            logger.error(
                "Database configuration failed",
                extra={
                    **_event(
                        "database.configure",
                        "failure",
                        perf_counter_ns() - started_at,
                    ),
                    "error": {"type": type(exc).__name__},
                },
            )
            raise

        _engine = engine
        _session_factory = session_factory
        logger.info(
            "Database configured",
            extra=_event(
                "database.configure",
                "success",
                perf_counter_ns() - started_at,
            ),
        )


async def get_session() -> AsyncIterator[AsyncSession]:

    session_factory = _session_factory
    if session_factory is None:
        raise RuntimeError(
            "Database is not configured. Call configure_database() first."
        )

    started_at = perf_counter_ns()
    outcome = "success"
    async with session_factory() as session:
        try:
            yield session
        except Exception as exc:
            outcome = "failure"
            rollback_started_at = perf_counter_ns()
            try:
                await session.rollback()
                logger.warning(
                    "Database session rolled back",
                    extra=_event(
                        "database.rollback",
                        "success",
                        perf_counter_ns() - rollback_started_at,
                    ),
                )
            except Exception as rollback_exc:
                logger.error(
                    "Database session rollback failed",
                    extra={
                        **_event(
                            "database.rollback",
                            "failure",
                            perf_counter_ns() - rollback_started_at,
                        ),
                        "error": {"type": type(rollback_exc).__name__},
                    },
                )
            logger.error(
                "Database session operation failed",
                extra={
                    **_event(
                        "database.session",
                        "failure",
                        perf_counter_ns() - started_at,
                    ),
                    "error": {"type": type(exc).__name__},
                },
            )
            raise
        finally:
            logger.info(
                "Database session completed",
                extra=_event(
                    "database.session",
                    outcome,
                    perf_counter_ns() - started_at,
                ),
            )


async def dispose_database() -> None:

    global _engine, _session_factory

    with _configuration_lock:
        engine = _engine
        _engine = None
        _session_factory = None

    if engine is None:
        return

    started_at = perf_counter_ns()
    try:
        await engine.dispose()
    except Exception as exc:
        logger.error(
            "Database disposal failed",
            extra={
                **_event(
                    "database.dispose",
                    "failure",
                    perf_counter_ns() - started_at,
                ),
                "error": {"type": type(exc).__name__},
            },
        )
        raise

    logger.info(
        "Database disposed",
        extra=_event(
            "database.dispose",
            "success",
            perf_counter_ns() - started_at,
        ),
    )
