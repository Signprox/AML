from fastapi import FastAPI

from app.core.config import get_settings


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="Anti-Money Laundering backend service.",
    version="0.1.0",
    debug=settings.debug,
)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
