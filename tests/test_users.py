from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_create_user_use_case, get_get_user_use_case
from app.api.v1 import router as v1_router
from app.api.v2 import router as v2_router
from app.application.exceptions import NotFoundError, UserAlreadyExistsError
from app.application.use_cases import CreateUserCommand, CreateUserUseCase, GetUserUseCase
from app.core.handlers import register_exception_handlers
from app.core.middleware import RequestLoggingMiddleware
from app.domain.entities import User
from app.infrastructure.database.models import UserModel


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"


class MemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self.users.values() if u.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def add(self, user: User) -> User:
        self.users[user.id] = user
        return user


class MemoryUnitOfWork:
    def __init__(self, repository: MemoryUserRepository) -> None:
        self.users = repository
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_commits() -> None:
    repository = MemoryUserRepository()
    unit_of_work = MemoryUnitOfWork(repository)
    use_case = CreateUserUseCase(unit_of_work, FakeHasher())

    user = await use_case.execute(
        CreateUserCommand(
            username="test.user",
            email="TEST@EXAMPLE.COM",
            password="strong-password",
        )
    )

    assert user.email == "test@example.com"
    assert user.password_hash == "hashed:strong-password"
    assert user.role == "user"
    assert unit_of_work.commits == 1


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_username() -> None:
    repository = MemoryUserRepository()
    existing = sample_user(username="existing")
    repository.users[existing.id] = existing
    use_case = CreateUserUseCase(MemoryUnitOfWork(repository), FakeHasher())

    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(
            CreateUserCommand(
                username="existing",
                email="different@example.com",
                password="strong-password",
            )
        )


def sample_user(**overrides) -> User:
    now = datetime.now(UTC)
    values = {
        "id": uuid4(),
        "username": "test.user",
        "email": "test@example.com",
        "password_hash": "never-return-this",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "is_verified": False,
        "role": "user",
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return User(**values)


def create_api_client(repository: MemoryUserRepository) -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)
    app.include_router(v1_router)
    app.include_router(v2_router)
    uow = MemoryUnitOfWork(repository)
    app.dependency_overrides[get_create_user_use_case] = lambda: CreateUserUseCase(
        uow, FakeHasher()
    )
    app.dependency_overrides[get_get_user_use_case] = lambda: GetUserUseCase(repository)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_create_and_get_user_api_never_exposes_password_hash(version: str) -> None:
    create_path = (
        "/api/v1/users/createUser" if version == "v1" else "/api/v2/users"
    )
    with create_api_client(MemoryUserRepository()) as client:
        created = client.post(
            create_path,
            json={
                "username": "api.user",
                "email": "api@example.com",
                "password": "strong-password",
                "first_name": "API",
            },
        )

        assert created.status_code == 201
        created_body = created.json()
        user_id = created_body["data"]["id"]
        assert "password" not in created.text
        assert created_body["data"]["role"] == "user"

        get_path = (
            f"/api/v1/users/getUser/{user_id}"
            if version == "v1"
            else f"/api/v2/users/{user_id}"
        )
        fetched = client.get(get_path)
        assert fetched.status_code == 200
        assert fetched.json()["data"]["id"] == user_id
        assert "password" not in fetched.text


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_get_unknown_user_returns_standard_not_found(version: str) -> None:
    user_id = uuid4()
    get_path = (
        f"/api/v1/users/getUser/{user_id}"
        if version == "v1"
        else f"/api/v2/users/{user_id}"
    )
    with create_api_client(MemoryUserRepository()) as client:
        response = client.get(get_path)

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


def test_user_model_matches_required_table_shape() -> None:
    table = UserModel.__table__
    assert table.name == "sm_user_t"
    assert set(table.columns) == {
        table.c.id,
        table.c.username,
        table.c.email,
        table.c.password_hash,
        table.c.first_name,
        table.c.last_name,
        table.c.is_active,
        table.c.is_verified,
        table.c.role,
        table.c.created_at,
        table.c.updated_at,
    }
    assert {index.name for index in table.indexes} == {
        "idx_users_email",
        "idx_users_username",
    }
