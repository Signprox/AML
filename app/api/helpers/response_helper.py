from typing import Any

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from app.api.schemas import ApiError, ApiResponse, PaginationMeta, ResponseMeta
from app.core.config import (
    DEFAULT_SUCCESS_MESSAGE,
    REQUEST_ID_HEADER,
    UNKNOWN_REQUEST_ID,
)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", UNKNOWN_REQUEST_ID)


def _headers(request: Request, headers: dict[str, str] | None = None) -> dict[str, str]:
    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = _request_id(request)
    return response_headers


def _content(response: ApiResponse[Any]) -> dict[str, Any]:
    content = jsonable_encoder(response, exclude_none=False)
    if response.meta.pagination is None:
        content["meta"].pop("pagination", None)
    return content


def success_response(
    request: Request,
    *,
    data: Any = None,
    message: str = DEFAULT_SUCCESS_MESSAGE,
    status_code: int = status.HTTP_200_OK,
    pagination: PaginationMeta | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = ApiResponse[Any](
        success=True,
        message=message,
        data=data,
        error=None,
        meta=ResponseMeta(request_id=_request_id(request), pagination=pagination),
    )
    return JSONResponse(
        status_code=status_code,
        content=_content(response),
        headers=_headers(request, headers),
    )


def error_response(
    request: Request,
    *,
    message: str,
    error_code: str,
    status_code: int,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = ApiResponse[Any](
        success=False,
        message=message,
        data=None,
        error=ApiError(code=error_code, details=details or []),
        meta=ResponseMeta(request_id=_request_id(request)),
    )
    return JSONResponse(
        status_code=status_code,
        content=_content(response),
        headers=_headers(request, headers),
    )
