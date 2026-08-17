import logging
import re
from time import perf_counter_ns
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import REQUEST_ID_HEADER


logger = logging.getLogger("aml.http")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        supplied_request_id = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = (
            supplied_request_id
            if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else uuid4().hex
        )
        request.state.request_id = request_id
        started_at = perf_counter_ns()

        try:
            response = await call_next(request)
        except Exception as exc:
            request.state.unhandled_exception_logged = True
            self._log_request(
                request=request,
                request_id=request_id,
                status_code=500,
                duration_ns=perf_counter_ns() - started_at,
                unhandled=True,
            )
            # Handle here, inside FastAPI's debug middleware, so clients never
            # receive framework tracebacks. The import is local to avoid a module
            # cycle between response helpers and the request-ID constant.
            from app.core.handlers.exception_handlers import (
                unexpected_exception_handler,
            )

            return await unexpected_exception_handler(request, exc)

        response.headers[REQUEST_ID_HEADER] = request_id
        self._log_request(
            request=request,
            request_id=request_id,
            status_code=response.status_code,
            duration_ns=perf_counter_ns() - started_at,
            unhandled=False,
        )
        return response

    @staticmethod
    def _log_request(
        request: Request,
        request_id: str,
        status_code: int,
        duration_ns: int,
        unhandled: bool,
    ) -> None:
        extra = {
            "client": {
                "address": request.client.host if request.client else None,
            },
            "event": {
                "dataset": "aml.http",
                "duration": duration_ns,
                "outcome": (
                    "failure" if unhandled or status_code >= 400 else "success"
                ),
            },
            "http": {
                "request": {"method": request.method},
                "response": {"status_code": status_code},
            },
            "trace": {"id": request_id},
            "url": {"path": request.url.path},
        }
        if unhandled:
            logger.exception("Unhandled request failure", extra=extra)
        else:
            logger.info("HTTP request completed", extra=extra)

