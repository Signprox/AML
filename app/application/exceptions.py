from typing import Any


class ApplicationError(Exception):
    """A safe, expected application failure that can be shown to API clients."""

    code = "APPLICATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class AuthenticationError(ApplicationError):
    code = "AUTHENTICATION_REQUIRED"


class AuthorizationError(ApplicationError):
    code = "FORBIDDEN"


class NotFoundError(ApplicationError):
    code = "NOT_FOUND"


class ConflictError(ApplicationError):
    code = "CONFLICT"
