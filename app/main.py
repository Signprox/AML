import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from app.api.helpers import error_response, success_response
from app.api.schemas import ApiResponse
from app.api.v1 import router as v1_router
from app.api.v2 import router as v2_router
from app.core.config import ApiErrorCode, get_settings
from app.core.handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware
from app.infrastructure.database import (
    check_database_connection,
    configure_database,
    dispose_database,
)

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger("aml.application")
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


@asynccontextmanager
async def lifespan(_: FastAPI):  # noqa: ANN201
    settings.validate_production_secrets()
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
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    SecurityHeadersMiddleware,
    enabled=settings.security_headers_enabled,
    hsts_enabled=settings.hsts_enabled,
    hsts_max_age=settings.hsts_max_age,
)
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
if settings.trusted_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)
register_exception_handlers(app)
app.include_router(v1_router)
app.include_router(v2_router)


@app.get("/health/live", tags=["Health"], response_model=ApiResponse[dict[str, str]])
@limiter.limit(settings.rate_limit)
def health_live(request: Request) -> JSONResponse:
    return success_response(
        request,
        data={"status": "alive"},
        message="Service is alive",
    )


@app.get("/health/ready", tags=["Health"], response_model=ApiResponse[dict[str, str]])
@limiter.limit(settings.rate_limit)
async def health_ready(request: Request) -> JSONResponse:
    db_ok = await check_database_connection()
    if not db_ok:
        return error_response(
            request,
            message="Database is unavailable",
            error_code=ApiErrorCode.INTERNAL_SERVER_ERROR,
            status_code=503,
        )
    return success_response(
        request,
        data={"status": "ready"},
        message="Service is ready",
    )


@app.get("/health", tags=["Health"], response_model=ApiResponse[dict[str, str]])
@limiter.limit(settings.rate_limit)
async def health_check(request: Request) -> JSONResponse:
    db_ok = await check_database_connection()
    status_value = "healthy" if db_ok else "degraded"
    if not db_ok:
        return error_response(
            request,
            message="Service is degraded",
            error_code=ApiErrorCode.INTERNAL_SERVER_ERROR,
            status_code=503,
            details=[{"message": "Database is unavailable", "type": "dependency_error"}],
        )
    return success_response(
        request,
        data={"status": status_value},
        message="Service is healthy",
    )
