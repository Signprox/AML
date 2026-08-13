import logging
from time import perf_counter_ns
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


logger = logging.getLogger("aml.http")
REQUEST_ID_HEADER = "X-Request-ID"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        started_at = perf_counter_ns()

        try:
            response = await call_next(request)
        except Exception:
            self._log_request(
                request=request,
                request_id=request_id,
                status_code=500,
                duration_ns=perf_counter_ns() - started_at,
                failed=True,
            )
            raise

        response.headers[REQUEST_ID_HEADER] = request_id
        self._log_request(
            request=request,
            request_id=request_id,
            status_code=response.status_code,
            duration_ns=perf_counter_ns() - started_at,
            failed=False,
        )
        return response

    @staticmethod
    def _log_request(
        request: Request,
        request_id: str,
        status_code: int,
        duration_ns: int,
        failed: bool,
    ) -> None:
        extra = {
            "client": {
                "address": request.client.host if request.client else None,
            },
            "event": {
                "dataset": "aml.http",
                "duration": duration_ns,
                "outcome": "failure" if failed else "success",
            },
            "http": {
                "request": {"method": request.method},
                "response": {"status_code": status_code},
            },
            "trace": {"id": request_id},
            "url": {"path": request.url.path},
        }
        if failed:
            logger.exception("Unhandled request failure", extra=extra)
        else:
            logger.info("HTTP request completed", extra=extra)

