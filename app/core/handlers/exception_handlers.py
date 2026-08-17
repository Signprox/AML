import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.api.helpers import error_response
from app.application.exceptions import (
    ApplicationError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from app.core.config import (
    DEFAULT_HTTP_ERROR_MESSAGE,
    INTERNAL_ERROR_MESSAGE,
    UNKNOWN_REQUEST_ID,
    VALIDATION_ERROR_MESSAGE,
    ApiErrorCode,
)


logger = logging.getLogger("aml.exceptions")

_HTTP_ERROR_CODES = {
    status.HTTP_400_BAD_REQUEST: ApiErrorCode.BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED: ApiErrorCode.AUTHENTICATION_REQUIRED,
    status.HTTP_403_FORBIDDEN: ApiErrorCode.FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ApiErrorCode.NOT_FOUND,
    status.HTTP_405_METHOD_NOT_ALLOWED: ApiErrorCode.METHOD_NOT_ALLOWED,
    status.HTTP_409_CONFLICT: ApiErrorCode.CONFLICT,
    422: ApiErrorCode.UNPROCESSABLE_ENTITY,
    status.HTTP_429_TOO_MANY_REQUESTS: ApiErrorCode.RATE_LIMIT_EXCEEDED,
}

_APPLICATION_STATUS = {
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    AuthorizationError: status.HTTP_403_FORBIDDEN,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
}


def _validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    # Deliberately omit `input` and `ctx`, which may contain credentials or AML data.
    return [
        {
            "location": [str(part) for part in error.get("loc", ())],
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return error_response(
        request,
        message=VALIDATION_ERROR_MESSAGE,
        error_code=ApiErrorCode.VALIDATION_ERROR,
        status_code=422,
        details=_validation_details(exc),
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    default_message = (
        HTTPStatus(exc.status_code).phrase
        if exc.status_code in HTTPStatus._value2member_map_
        else DEFAULT_HTTP_ERROR_MESSAGE
    )
    message = exc.detail if isinstance(exc.detail, str) else default_message
    return error_response(
        request,
        message=message,
        error_code=_HTTP_ERROR_CODES.get(exc.status_code, ApiErrorCode.HTTP_ERROR),
        status_code=exc.status_code,
        headers=dict(exc.headers or {}),
    )


async def application_exception_handler(
    request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    status_code = next(
        (
            mapped_status
            for exception_type, mapped_status in _APPLICATION_STATUS.items()
            if isinstance(exc, exception_type)
        ),
        status.HTTP_400_BAD_REQUEST,
    )
    return error_response(
        request,
        message=exc.message,
        error_code=exc.code,
        status_code=status_code,
        details=exc.details,
    )


async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not getattr(request.state, "unhandled_exception_logged", False):
        logger.exception(
            "Unhandled request failure",
            exc_info=exc,
            extra={
                "trace": {
                    "id": getattr(request.state, "request_id", UNKNOWN_REQUEST_ID)
                }
            },
        )
    return error_response(
        request,
        message=INTERNAL_ERROR_MESSAGE,
        error_code=ApiErrorCode.INTERNAL_SERVER_ERROR,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(ApplicationError, application_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
