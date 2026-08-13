import logging
import logging.config
from threading import Lock

from app.core.config import Settings


_configuration_lock = Lock()
_configured_signature: tuple[str, str, str] | None = None


class ServiceContextFilter(logging.Filter):
    def __init__(self, service_name: str, service_environment: str) -> None:
        super().__init__()
        self.service_name = service_name
        self.service_environment = service_environment

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "service"):
            record.service = {
                "name": self.service_name,
                "environment": self.service_environment,
            }
        if not hasattr(record, "event"):
            record.event = {"dataset": "aml.application"}
        return True


def configure_logging(settings: Settings) -> None:
    """Configure ECS console logging once for the active settings."""
    global _configured_signature

    signature = (settings.app_name, settings.app_env, settings.log_level)
    with _configuration_lock:
        if _configured_signature == signature:
            return

        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "filters": {
                    "service_context": {
                        "()": ServiceContextFilter,
                        "service_name": settings.app_name,
                        "service_environment": settings.app_env,
                    }
                },
                "formatters": {
                    "ecs": {
                        "()": "ecs_logging.StdlibFormatter",
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "filters": ["service_context"],
                        "formatter": "ecs",
                        "level": settings.log_level,
                        "stream": "ext://sys.stdout",
                    }
                },
                "root": {
                    "handlers": ["console"],
                    "level": settings.log_level,
                },
                "loggers": {
                    "uvicorn": {
                        "handlers": ["console"],
                        "level": settings.log_level,
                        "propagate": False,
                    },
                    "uvicorn.error": {
                        "handlers": ["console"],
                        "level": settings.log_level,
                        "propagate": False,
                    },
                    # RequestLoggingMiddleware replaces Uvicorn access logs because
                    # Uvicorn includes raw query strings in its access message.
                    "uvicorn.access": {
                        "handlers": [],
                        "level": "CRITICAL",
                        "propagate": False,
                    }
                },
            }
        )
        _configured_signature = signature
