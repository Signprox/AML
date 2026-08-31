from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import NotFoundError, UserAlreadyExistsError
from app.application.interfaces import UserRepository
from app.domain.entities import User
from app.infrastructure.database import DatabaseHelper
from app.infrastructure.database.models import UserModel


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        username=model.username,
        email=model.email,
        password_hash=model.password_hash,
        first_name=model.first_name,
        last_name=model.last_name,
        is_active=model.is_active,
        is_verified=model.is_verified,
        role=model.role,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _apply_domain_to_model(user: User, model: UserModel) -> None:
    model.username = user.username
    model.email = user.email
    model.password_hash = user.password_hash
    model.first_name = user.first_name
    model.last_name = user.last_name
    model.is_active = user.is_active
    model.is_verified = user.is_verified
    model.role = user.role
    model.updated_at = user.updated_at


class SqlUserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._database = DatabaseHelper(session)

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._database.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def get_by_username(self, username: str) -> User | None:
        result = await self._database.execute(
            select(UserModel).where(UserModel.username == username)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._database.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def add(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            role=user.role,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        self._session.add(model)
        try:
            await self._database.flush()
        except IntegrityError as exc:
            raise UserAlreadyExistsError("Username or email is already registered") from exc
        return _to_domain(model)

    async def update(self, user: User) -> User:
        result = await self._database.execute(
            select(UserModel).where(UserModel.id == user.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise NotFoundError("User not found")

        _apply_domain_to_model(user, model)
        try:
            updated_model = await self._database.update(model)
        except IntegrityError as exc:
            raise UserAlreadyExistsError("Username or email is already registered") from exc
        return _to_domain(updated_model)


class SqlAlchemyUserUnitOfWork:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._database = DatabaseHelper(session)
        self.users: UserRepository = SqlUserRepository(session)

    async def commit(self) -> None:
        await self._database.commit()
