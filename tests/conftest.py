"""Shared test fixtures."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_authenticate_user_use_case,
    get_create_user_use_case,
    get_get_user_use_case,
    get_login_use_case,
    get_token_service,
)
from app.api.v1 import router as v1_router
from app.api.v2 import router as v2_router
from app.application.exceptions import NotFoundError
from app.application.use_cases.user import (
    AuthenticateUserUseCase,
    CreateUserUseCase,
    GetUserUseCase,
    LoginUseCase,
)
from app.core.handlers import register_exception_handlers
from app.core.middleware import RequestLoggingMiddleware
from app.domain.entities import User

STRONG_PASSWORD = "StrongPass1!"


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


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

    async def update(self, user: User) -> User:
        if user.id not in self.users:
            raise NotFoundError("User not found")
        self.users[user.id] = user
        return user


class MemoryUnitOfWork:
    def __init__(self, repository: MemoryUserRepository) -> None:
        self.users = repository
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class MemoryAuditRepository:
    def __init__(self) -> None:
        self.events = []

    async def add(self, event):
        self.events.append(event)
        return event


def sample_user(**overrides) -> User:
    now = datetime.now(UTC)
    values = {
        "id": uuid4(),
        "username": "test.user",
        "email": "test@example.com",
        "password_hash": "hashed:StrongPass1!",
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
        uow, FakeHasher(), MemoryAuditRepository()
    )
    app.dependency_overrides[get_get_user_use_case] = lambda: GetUserUseCase(
        repository, MemoryAuditRepository()
    )
    app.dependency_overrides[get_login_use_case] = lambda: LoginUseCase(
        repository,
        FakeHasher(),
        _FakeTokenService(),
        MemoryAuditRepository(),
    )
    app.dependency_overrides[get_authenticate_user_use_case] = lambda: (
        AuthenticateUserUseCase(repository)
    )
    app.dependency_overrides[get_token_service] = lambda: _FakeTokenService()
    return TestClient(app, raise_server_exceptions=False)


class _FakeTokenService:
    def create_token(self, subject: str, claims=None) -> str:
        return f"token-for-{subject}"

    def decode_token(self, token: str) -> dict:
        from app.application.exceptions import AuthenticationError

        if not token.startswith("token-for-"):
            raise AuthenticationError("Invalid or expired token")
        return {"sub": token.removeprefix("token-for-")}
