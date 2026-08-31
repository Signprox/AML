import re

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InvalidEmailError(ValueError):
    pass


class Email:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        normalized = value.strip().lower()
        if len(normalized) > 255:
            raise InvalidEmailError("Email must not exceed 255 characters")
        if not _EMAIL_PATTERN.match(normalized):
            raise InvalidEmailError("Email format is invalid")
        self._value = normalized

    @property
    def value(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Email) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return self._value
