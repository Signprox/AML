from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.value_objects import Email, Username


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    username: str
    email: str
    password_hash: str
    first_name: str | None
    last_name: str | None
    is_active: bool
    is_verified: bool
    role: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        username: str,
        email: str,
        password_hash: str,
        first_name: str | None = None,
        last_name: str | None = None,
        role: str = "user",
    ) -> "User":
        validated_username = Username(username)
        validated_email = Email(email)
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            username=validated_username.value,
            email=validated_email.value,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_verified=False,
            role=role,
            created_at=now,
            updated_at=now,
        )

    def deactivate(self) -> "User":
        return User(
            id=self.id,
            username=self.username,
            email=self.email,
            password_hash=self.password_hash,
            first_name=self.first_name,
            last_name=self.last_name,
            is_active=False,
            is_verified=self.is_verified,
            role=self.role,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
        )

    def verify(self) -> "User":
        return User(
            id=self.id,
            username=self.username,
            email=self.email,
            password_hash=self.password_hash,
            first_name=self.first_name,
            last_name=self.last_name,
            is_active=self.is_active,
            is_verified=True,
            role=self.role,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
        )
