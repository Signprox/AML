import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware


settings = get_settings()
configure_logging(settings)
logger = logging.getLogger("aml.application")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "Application started",
        extra={"event": {"action": "start", "dataset": "aml.application"}},
    )
    yield
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


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
