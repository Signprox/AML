import logging

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, Integer, Table, UniqueConstraint, select

from app.core.config import Settings
from app.infrastructure.database import Base, DatabaseHelper
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
        "db_pool_size": 5,
        "db_max_overflow": 10,
        "db_pool_timeout": 30,
        "jwt_secret": "test-secret",
        "jwt_algorithm": "HS256",
        "jwt_expire_minutes": 60,
        "cors_origins": "",
        "trusted_hosts": "",
        "rate_limit": "100/minute",
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


class FakeTransaction:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exception_type, *_args):
        if exception_type is None:
            self.session.commits += 1
        else:
            self.session.transaction_rollbacks += 1


class HelperSession:
    def __init__(self) -> None:
        self.executions = []
        self.result = object()
        self.commits = 0
        self.transaction_rollbacks = 0
        self.flushes = 0
        self.rollbacks = 0
        self.merges = []

    async def execute(self, statement, parameters=None):
        self.executions.append((statement, parameters))
        return self.result

    async def merge(self, instance):
        self.merges.append(instance)
        return instance

    def begin(self):
        return FakeTransaction(self)

    async def flush(self, _objects=None):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_database_helper_executes_statement_without_committing() -> None:
    session = HelperSession()
    helper = DatabaseHelper(session)
    statement = select(1)

    result = await helper.execute(statement, {"value": 1})

    assert result is session.result
    assert session.executions == [(statement, {"value": 1})]
    assert session.commits == 0


@pytest.mark.asyncio
async def test_database_helper_executes_parameterized_raw_query() -> None:
    session = HelperSession()
    helper = DatabaseHelper(session)

    await helper.execute_raw(
        "SELECT id FROM sm_user_t WHERE email=:email",
        {"email": "safe@example.com"},
    )

    statement, parameters = session.executions[0]
    assert str(statement) == "SELECT id FROM sm_user_t WHERE email=:email"
    assert parameters == {"email": "safe@example.com"}


@pytest.mark.asyncio
async def test_database_helper_rejects_empty_raw_query() -> None:
    helper = DatabaseHelper(HelperSession())

    with pytest.raises(ValueError, match="must not be empty"):
        await helper.execute_raw("   ")


@pytest.mark.asyncio
async def test_database_helper_transaction_commits_or_rolls_back() -> None:
    session = HelperSession()
    helper = DatabaseHelper(session)

    async with helper.transaction():
        pass
    assert session.commits == 1

    with pytest.raises(RuntimeError, match="failure"):
        async with helper.transaction():
            raise RuntimeError("failure")
    assert session.transaction_rollbacks == 1


@pytest.mark.asyncio
async def test_database_helper_flush_commit_and_rollback_are_explicit() -> None:
    session = HelperSession()
    helper = DatabaseHelper(session)

    await helper.flush()
    await helper.commit()
    await helper.rollback()

    assert session.flushes == 1
    assert session.commits == 1
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_database_helper_update_merges_and_flushes_without_committing() -> None:
    session = HelperSession()
    helper = DatabaseHelper(session)
    model = object()

    result = await helper.update(model)

    assert result is model
    assert session.merges == [model]
    assert session.flushes == 1
    assert session.commits == 0


@pytest.mark.asyncio
async def test_database_helper_logs_do_not_contain_query_or_parameters(caplog) -> None:
    helper = DatabaseHelper(HelperSession())
    query = "SELECT id FROM sm_user_t WHERE email=:email"
    secret_parameter = "must-not-appear@example.com"

    with caplog.at_level(logging.INFO, logger="aml.database"):
        await helper.execute_raw(query, {"email": secret_parameter})

    assert query not in caplog.text
    assert secret_parameter not in caplog.text
    assert any(
        record.event["action"] == "database.execute_raw" for record in caplog.records
    )
