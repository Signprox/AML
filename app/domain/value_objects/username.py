import re

_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class InvalidUsernameError(ValueError):
    pass


class Username:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        normalized = value.strip()
        if len(normalized) < 3 or len(normalized) > 50:
            raise InvalidUsernameError("Username must be between 3 and 50 characters")
        if not _USERNAME_PATTERN.match(normalized):
            raise InvalidUsernameError(
                "Username may only contain letters, numbers, underscores, dots, and hyphens"
            )
        self._value = normalized

    @property
    def value(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Username) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return self._value
