from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.application.exceptions import AuthenticationError
from app.core.config import Settings


class JwtTokenService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._expire_minutes = settings.jwt_expire_minutes

    def create_token(self, subject: str, claims: dict[str, Any] | None = None) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(minutes=self._expire_minutes),
        }
        if claims:
            payload.update(claims)
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired token") from exc
