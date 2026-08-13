from collections.abc import Iterable

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Enforce the application's defensive HTTP response-header policy."""

    _STANDARD_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
    _CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'"
    _CSP_EXCLUDED_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool = True,
        hsts_enabled: bool = False,
        hsts_max_age: int = 31_536_000,
        csp_excluded_paths: Iterable[str] | None = None,
    ) -> None:
        if hsts_max_age < 0:
            raise ValueError("hsts_max_age must be non-negative")

        self.app = app
        self.enabled = enabled
        self.hsts_enabled = hsts_enabled
        self.hsts_value = f"max-age={hsts_max_age}; includeSubDomains"
        self.csp_excluded_paths = frozenset(
            csp_excluded_paths or self._CSP_EXCLUDED_PATHS
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.enabled or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self._STANDARD_HEADERS.items():
                    headers[name] = value

                if path not in self.csp_excluded_paths:
                    headers["Content-Security-Policy"] = self._CONTENT_SECURITY_POLICY
                elif "Content-Security-Policy" in headers:
                    del headers["Content-Security-Policy"]

                if self.hsts_enabled:
                    headers["Strict-Transport-Security"] = self.hsts_value
                elif "Strict-Transport-Security" in headers:
                    del headers["Strict-Transport-Security"]

            await send(message)

        await self.app(scope, receive, send_with_security_headers)

