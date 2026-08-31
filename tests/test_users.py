from uuid import uuid4

import pytest

from app.application.exceptions import NotFoundError, UserAlreadyExistsError
from app.application.use_cases import CreateUserCommand, CreateUserUseCase
from app.domain.entities import User
from app.infrastructure.database.models import UserModel
from tests.conftest import (
    STRONG_PASSWORD,
    FakeHasher,
    MemoryAuditRepository,
    MemoryUnitOfWork,
    MemoryUserRepository,
    create_api_client,
    sample_user,
)


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_commits() -> None:
    repository = MemoryUserRepository()
    unit_of_work = MemoryUnitOfWork(repository)
    use_case = CreateUserUseCase(unit_of_work, FakeHasher(), MemoryAuditRepository())

    user = await use_case.execute(
        CreateUserCommand(
            username="test.user",
            email="TEST@EXAMPLE.COM",
            password=STRONG_PASSWORD,
        )
    )

    assert user.email == "test@example.com"
    assert user.password_hash == f"hashed:{STRONG_PASSWORD}"
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
                password=STRONG_PASSWORD,
            )
        )


@pytest.mark.asyncio
async def test_update_user_persists_changes() -> None:
    repository = MemoryUserRepository()
    existing = sample_user(first_name="Before")
    repository.users[existing.id] = existing
    updated = User(
        id=existing.id,
        username=existing.username,
        email=existing.email,
        password_hash=existing.password_hash,
        first_name="After",
        last_name=existing.last_name,
        is_active=existing.is_active,
        is_verified=True,
        role=existing.role,
        created_at=existing.created_at,
        updated_at=existing.updated_at,
    )

    result = await repository.update(updated)

    assert result.first_name == "After"
    assert result.is_verified is True
    assert repository.users[existing.id].first_name == "After"


@pytest.mark.asyncio
async def test_update_unknown_user_raises_not_found() -> None:
    repository = MemoryUserRepository()

    with pytest.raises(NotFoundError):
        await repository.update(sample_user())


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_create_and_get_user_api_never_exposes_password_hash(version: str) -> None:
    create_path = (
        "/api/v1/users/createUser" if version == "v1" else "/api/v2/users"
    )
    login_path = (
        "/api/v1/users/login" if version == "v1" else "/api/v2/users/login"
    )
    with create_api_client(MemoryUserRepository()) as client:
        created = client.post(
            create_path,
            json={
                "username": "api.user",
                "email": "api@example.com",
                "password": STRONG_PASSWORD,
                "first_name": "API",
            },
        )

        assert created.status_code == 201
        created_body = created.json()
        user_id = created_body["data"]["id"]
        assert "password" not in created.text
        assert created_body["data"]["role"] == "user"

        login = client.post(
            login_path,
            json={"username": "api.user", "password": STRONG_PASSWORD},
        )
        assert login.status_code == 200
        token = login.json()["data"]["access_token"]

        get_path = (
            f"/api/v1/users/getUser/{user_id}"
            if version == "v1"
            else f"/api/v2/users/{user_id}"
        )
        fetched = client.get(get_path, headers={"Authorization": f"Bearer {token}"})
        assert fetched.status_code == 200
        assert fetched.json()["data"]["id"] == user_id
        assert "password" not in fetched.text


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_get_unknown_user_returns_standard_not_found(version: str) -> None:
    repository = MemoryUserRepository()
    user = sample_user(username="auth.user")
    repository.users[user.id] = user
    user_id = uuid4()
    get_path = (
        f"/api/v1/users/getUser/{user_id}"
        if version == "v1"
        else f"/api/v2/users/{user_id}"
    )
    with create_api_client(repository) as client:
        unauthenticated = client.get(get_path)
        assert unauthenticated.status_code == 401

        token = f"token-for-{user.id}"
        response = client.get(get_path, headers={"Authorization": f"Bearer {token}"})
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
