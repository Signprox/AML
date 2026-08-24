from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases import CreateUserUseCase, GetUserUseCase
from app.infrastructure.database import get_session
from app.infrastructure.repositories import SqlAlchemyUserUnitOfWork, SqlUserRepository
from app.infrastructure.security import Argon2PasswordHasher


_password_hasher = Argon2PasswordHasher()


def get_create_user_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreateUserUseCase:
    return CreateUserUseCase(SqlAlchemyUserUnitOfWork(session), _password_hasher)


def get_get_user_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetUserUseCase:
    return GetUserUseCase(SqlUserRepository(session))
