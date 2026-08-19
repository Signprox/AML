import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from app.api.helpers import success_response
from app.api.schemas import ApiResponse
from app.core.config import get_settings
from app.core.handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware
from app.infrastructure.database import configure_database, dispose_database


settings = get_settings()
configure_logging(settings)
logger = logging.getLogger("aml.application")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_database(settings)
    logger.info(
        "Application started",
        extra={"event": {"action": "start", "dataset": "aml.application"}},
    )
    try:
        yield
    finally:
        await dispose_database()
        logger.info(
            "Application stopped",
            extra={"event": {"action": "stop", "dataset": "aml.application"}},
        )


app = FastAPI(
    title=settings.app_name,
    description="Anti-Money Laundering backend service.",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    SecurityHeadersMiddleware,
    enabled=settings.security_headers_enabled,
    hsts_enabled=settings.hsts_enabled,
    hsts_max_age=settings.hsts_max_age,
)
register_exception_handlers(app)


@app.get("/health", tags=["Health"], response_model=ApiResponse[dict[str, str]])
def health_check(request: Request) -> JSONResponse:
    return success_response(
        request,
        data={"status": "healthy"},
        message="Service is healthy",
    )
