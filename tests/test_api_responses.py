import json

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.helpers import success_response
from app.api.schemas import PaginationMeta
from app.application.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
)
from app.core.handlers import register_exception_handlers
from app.core.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware
from app.core.config import ApiErrorCode


class ExampleInput(BaseModel):
    name: str
    secret: str


def create_test_app() -> FastAPI:
    test_app = FastAPI(debug=True)
    test_app.add_middleware(RequestLoggingMiddleware)
    test_app.add_middleware(SecurityHeadersMiddleware)
    register_exception_handlers(test_app)

    @test_app.get("/success")
    def success(request: Request):
        return success_response(request, data={"value": 1}, message="Success")

    @test_app.post("/created")
    def created(request: Request):
        return success_response(
            request,
            data={"id": 1},
            message="Created",
            status_code=status.HTTP_201_CREATED,
        )

    @test_app.get("/empty")
    def empty(request: Request):
        return success_response(request, data=None, message="No content")

    @test_app.get("/paginated")
    def paginated(request: Request):
        return success_response(
            request,
            data=[{"id": 1}],
            pagination=PaginationMeta(
                page=1,
                page_size=20,
                total=1,
                total_pages=1,
            ),
        )

    @test_app.post("/validate")
    def validate(_: ExampleInput, request: Request):
        return success_response(request)

    @test_app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="Record not found")

    @test_app.get("/conflict")
    def conflict():
        raise ConflictError("Record already exists")

    @test_app.get("/unauthenticated")
    def unauthenticated():
        raise AuthenticationError("Authentication required")

    @test_app.get("/forbidden")
    def forbidden():
        raise AuthorizationError("Permission denied")

    @test_app.get("/unexpected")
    def unexpected():
        raise RuntimeError("sensitive internal detail")

    return test_app


client = TestClient(create_test_app(), raise_server_exceptions=False)


def test_api_error_code_serializes_as_its_public_string() -> None:
    assert json.dumps({"code": ApiErrorCode.CONFLICT}) == '{"code": "CONFLICT"}'


def assert_envelope(response, *, success: bool, request_id: str) -> dict:
    body = response.json()
    assert set(body) == {"success", "message", "data", "error", "meta"}
    assert body["success"] is success
    assert body["meta"]["request_id"] == request_id
    assert response.headers["X-Request-ID"] == request_id
    return body


def test_success_response_contract() -> None:
    response = client.get("/success", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    body = assert_envelope(response, success=True, request_id="request-123")
    assert body["data"] == {"value": 1}
    assert body["error"] is None
    assert body["meta"] == {"request_id": "request-123"}


def test_created_and_empty_responses_preserve_semantics() -> None:
    created = client.post("/created", headers={"X-Request-ID": "created-1"})
    empty = client.get("/empty", headers={"X-Request-ID": "empty-1"})

    assert created.status_code == 201
    assert assert_envelope(created, success=True, request_id="created-1")["data"] == {"id": 1}
    assert assert_envelope(empty, success=True, request_id="empty-1")["data"] is None


def test_paginated_response_places_pagination_in_meta() -> None:
    response = client.get("/paginated", headers={"X-Request-ID": "page-1"})

    body = assert_envelope(response, success=True, request_id="page-1")
    assert body["meta"]["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": 1,
        "total_pages": 1,
    }


def test_invalid_external_request_id_is_replaced() -> None:
    response = client.get("/success", headers={"X-Request-ID": "not valid!"})

    body = response.json()
    assert body["meta"]["request_id"] != "not valid!"
    assert response.headers["X-Request-ID"] == body["meta"]["request_id"]


def test_validation_errors_are_standardized_without_input_values() -> None:
    response = client.post(
        "/validate",
        headers={"X-Request-ID": "validation-1"},
        json={"name": 123, "secret": {"password": "must-not-leak"}},
    )

    assert response.status_code == 422
    body = assert_envelope(response, success=False, request_id="validation-1")
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "must-not-leak" not in response.text


def test_http_and_application_errors_are_standardized() -> None:
    missing = client.get("/missing", headers={"X-Request-ID": "missing-1"})
    conflict = client.get("/conflict", headers={"X-Request-ID": "conflict-1"})

    assert missing.status_code == 404
    assert assert_envelope(missing, success=False, request_id="missing-1")["error"]["code"] == "NOT_FOUND"
    assert conflict.status_code == 409
    assert assert_envelope(conflict, success=False, request_id="conflict-1")["error"]["code"] == "CONFLICT"


def test_authentication_and_authorization_errors_preserve_statuses() -> None:
    unauthenticated = client.get(
        "/unauthenticated", headers={"X-Request-ID": "authn-1"}
    )
    forbidden = client.get("/forbidden", headers={"X-Request-ID": "authz-1"})

    assert unauthenticated.status_code == 401
    assert assert_envelope(
        unauthenticated, success=False, request_id="authn-1"
    )["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert forbidden.status_code == 403
    assert assert_envelope(forbidden, success=False, request_id="authz-1")[
        "error"
    ]["code"] == "FORBIDDEN"


def test_unexpected_errors_are_sanitized() -> None:
    response = client.get("/unexpected", headers={"X-Request-ID": "failure-1"})

    assert response.status_code == 500
    body = assert_envelope(response, success=False, request_id="failure-1")
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "sensitive internal detail" not in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_documentation_routes_keep_native_formats() -> None:
    docs = client.get("/docs")
    openapi = client.get("/openapi.json")

    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert openapi.status_code == 200
    assert "openapi" in openapi.json()
    assert "success" not in openapi.json()
