import logging

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, Integer, Table, UniqueConstraint

from app.core.config import Settings
from app.infrastructure.database import Base
from app.infrastructure.database import session as database_session


def make_settings(**overrides) -> Settings:
    values = {
        "app_name": "AML Backend",
        "app_env": "development",
        "debug": True,
        "log_level": "INFO",
        "security_headers_enabled": True,
        "hsts_enabled": False,
        "hsts_max_age": 31536000,
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "aml",
        "db_user": "aml",
        "db_password": "safe-password",
    }
    values.update(overrides)
    return Settings(**values)


def test_settings_build_encoded_async_database_url_and_mask_secret() -> None:
    settings = make_settings(
        db_user="user@example.com",
        db_password="p@ss:/?#[] word",
        db_name="aml records",
    )

    assert settings.database_url == (
        "postgresql+asyncpg://user%40example.com:"
        "p%40ss%3A%2F%3F%23%5B%5D%20word@localhost:5432/aml%20records"
    )
    assert "p@ss" not in repr(settings)
    assert "**********" in repr(settings)


@pytest.mark.parametrize("field", ["db_host", "db_name", "db_user"])
def test_settings_reject_empty_database_text(field: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: "   "})


@pytest.mark.parametrize("port", [0, 65536])
def test_settings_reject_invalid_database_port(port: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(db_port=port)


def test_base_metadata_uses_stable_constraint_names() -> None:
    table = Table(
        "naming_test",
        Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("value", Integer),
        UniqueConstraint("value"),
    )

    names = {constraint.name for constraint in table.constraints}
    assert "pk_naming_test" in names
    assert "uq_naming_test_value" in names
    Base.metadata.remove(table)


class FakeSession:
    def __init__(self) -> None:
        self.rolled_back = False
        self.closed = False

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, *_args) -> None:
        self.session.closed = True


@pytest.mark.asyncio
async def test_get_session_rolls_back_and_closes_without_committing(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        database_session,
        "_session_factory",
        lambda: FakeSessionContext(session),
    )

    dependency = database_session.get_session()
    assert await dependency.__anext__() is session

    with pytest.raises(RuntimeError, match="operation failed"):
        await dependency.athrow(RuntimeError("operation failed"))

    assert session.rolled_back is True
    assert session.closed is True
    assert not hasattr(session, "commit")


@pytest.mark.asyncio
async def test_get_session_requires_configuration(monkeypatch) -> None:
    monkeypatch.setattr(database_session, "_session_factory", None)

    with pytest.raises(RuntimeError, match="configure_database"):
        await database_session.get_session().__anext__()


class FakeEngine:
    def __init__(self) -> None:
        self.dispose_calls = 0

    async def dispose(self) -> None:
        self.dispose_calls += 1


@pytest.mark.asyncio
async def test_dispose_database_is_repeatable(monkeypatch) -> None:
    engine = FakeEngine()
    monkeypatch.setattr(database_session, "_engine", engine)
    monkeypatch.setattr(database_session, "_session_factory", object())

    await database_session.dispose_database()
    await database_session.dispose_database()

    assert engine.dispose_calls == 1
    assert database_session._engine is None
    assert database_session._session_factory is None


def test_configuration_log_does_not_expose_url_or_password(monkeypatch, caplog) -> None:
    settings = make_settings(db_password="must-not-appear")
    engine = FakeEngine()
    monkeypatch.setattr(database_session, "_engine", None)
    monkeypatch.setattr(database_session, "_session_factory", None)
    monkeypatch.setattr(database_session, "create_async_engine", lambda *_a, **_k: engine)
    monkeypatch.setattr(database_session, "async_sessionmaker", lambda **_k: object())

    with caplog.at_level(logging.INFO, logger="aml.database"):
        database_session.configure_database(settings)

    messages = caplog.text
    assert "must-not-appear" not in messages
    assert settings.database_url not in messages
    assert "Database configured" in messages


def test_configure_database_is_idempotent(monkeypatch) -> None:
    settings = make_settings()
    engine = FakeEngine()
    calls = 0

    def create_engine(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return engine

    monkeypatch.setattr(database_session, "_engine", None)
    monkeypatch.setattr(database_session, "_session_factory", None)
    monkeypatch.setattr(database_session, "create_async_engine", create_engine)
    monkeypatch.setattr(database_session, "async_sessionmaker", lambda **_k: object())

    database_session.configure_database(settings)
    database_session.configure_database(settings)

    assert calls == 1
