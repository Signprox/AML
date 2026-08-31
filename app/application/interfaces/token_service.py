from typing import Any, Protocol


class TokenService(Protocol):
    def create_token(self, subject: str, claims: dict[str, Any] | None = None) -> str: ...

    def decode_token(self, token: str) -> dict[str, Any]: ...
