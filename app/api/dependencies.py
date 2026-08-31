from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import AuthenticationError, AuthorizationError
from app.application.interfaces import PasswordHasher
from app.application.use_cases.user import (
    AuthenticateUserUseCase,
    CreateUserUseCase,
    GetUserUseCase,
    LoginUseCase,
)
from app.core.config import Settings, get_settings
from app.domain.entities import User
from app.infrastructure.database import get_session
from app.infrastructure.repositories import (
    SqlAlchemyUserUnitOfWork,
    SqlAuditRepository,
    SqlUserRepository,
)
from app.infrastructure.security import Argon2PasswordHasher, JwtTokenService

_bearer_scheme = HTTPBearer(auto_error=False)


def get_password_hasher() -> PasswordHasher:
    return Argon2PasswordHasher()


def get_settings_dependency() -> Settings:
    return get_settings()


def get_token_service(
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> JwtTokenService:
    return JwtTokenService(settings)


def _audit_repository(session: AsyncSession) -> SqlAuditRepository:
    return SqlAuditRepository(session)


def get_create_user_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
) -> CreateUserUseCase:
    unit_of_work = SqlAlchemyUserUnitOfWork(session)
    return CreateUserUseCase(
        unit_of_work,
        password_hasher,
        _audit_repository(session),
    )


def get_get_user_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetUserUseCase:
    return GetUserUseCase(
        SqlUserRepository(session),
        _audit_repository(session),
    )


def get_login_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    token_service: Annotated[JwtTokenService, Depends(get_token_service)],
) -> LoginUseCase:
    return LoginUseCase(
        SqlUserRepository(session),
        password_hasher,
        token_service,
        _audit_repository(session),
    )


def get_authenticate_user_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthenticateUserUseCase:
    return AuthenticateUserUseCase(SqlUserRepository(session))


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    authenticate_use_case: Annotated[
        AuthenticateUserUseCase, Depends(get_authenticate_user_use_case)
    ],
    token_service: Annotated[JwtTokenService, Depends(get_token_service)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication required")
    payload = token_service.decode_token(credentials.credentials)
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise AuthenticationError("Invalid token subject")
    return await authenticate_use_case.execute(UUID(subject))


def require_roles(*roles: str) -> Callable[..., Awaitable[User]]:
    async def _require_roles(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise AuthorizationError("Permission denied")
        return current_user

    return _require_roles