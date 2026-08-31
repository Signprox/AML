# AML Backend

FastAPI foundation for an Anti-Money Laundering (AML) backend, organized with Clean Architecture and Domain-Driven Design (DDD) boundaries.

For a class-by-class explanation and end-to-end request flows, see
[`docs/ARCHITECTURE_GUIDE.md`](docs/ARCHITECTURE_GUIDE.md).

The repository provides the application scaffold, cross-cutting platform concerns, and initial system-user management: environment-aware configuration, Elastic Common Schema (ECS) logging, request correlation, security response headers, JWT authentication, health monitoring, database migrations, audit-event persistence, and interactive API documentation. AML business workflows and external integrations are not implemented yet.

## Contents

- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [Local setup](#local-setup)
- [Running the application](#running-the-application)
- [Configuration](#configuration)
- [API endpoints](#api-endpoints)
- [Logging and request correlation](#logging-and-request-correlation)
- [Security headers](#security-headers)
- [Adding application features](#adding-application-features)
- [Testing and verification](#testing-and-verification)
- [Current scope and roadmap](#current-scope-and-roadmap)

## Architecture

The application follows four primary layers. Dependencies should point inward toward business rules.

```text
API / Presentation
       |
       v
Application / Use Cases
       |
       v
Domain / Business Rules

Infrastructure implements interfaces owned by the application layer.
```

### Domain layer

Location: `app/domain/`

Contains pure business concepts and AML rules. It must not depend on FastAPI, Pydantic HTTP schemas, SQLAlchemy, or external service SDKs.

- `entities/`: domain entities
- `value_objects/`: validated primitives such as Email and Username

### Application layer

Location: `app/application/`

Coordinates business workflows without knowing how HTTP, databases, or third-party services work.

- `use_cases/`: application workflows grouped by entity (for example `user/`)
- `interfaces/`: repository and external-service contracts required by use cases

### Infrastructure layer

Location: `app/infrastructure/`

Contains technical adapters for interfaces defined by the application layer.

- `database/`: async database sessions, ORM models, and persistence configuration
- `repositories/`: concrete repository implementations (`SqlUserRepository`, `SqlAuditRepository`)
- `security/`: Argon2 password hashing and JWT token service

The async PostgreSQL session foundation, ORM models, and SQL repository implementations are implemented.

### API layer

Location: `app/api/`

Provides FastAPI presentation concerns.

- `v1/` and `v2/`: versioned routers with shared schemas and handlers
- `schemas/`: shared HTTP request/response models
- `handlers/`: shared route handler logic
- `dependencies.py`: FastAPI dependency injection wiring

Routers should validate HTTP input, call application use cases, and translate results into HTTP responses. They should not contain SQL queries or AML business rules.

### Core components

Location: `app/core/`

Contains application-wide technical concerns:

- `config/`: typed settings and environment-file selection
- `logging/`: ECS JSON logging configuration
- `middleware/`: request logging and response security policy

## Project structure

```text
AML/
|-- alembic/                         # Database migrations
|-- app/
|   |-- api/
|   |   |-- v1/                      # Legacy API paths
|   |   |-- v2/                      # RESTful API paths
|   |   |-- schemas/                 # Shared HTTP schemas
|   |   |-- handlers/                # Shared route handlers
|   |   `-- dependencies.py          # Dependency injection
|   |-- application/
|   |   |-- interfaces/              # Abstract repositories and gateways
|   |   `-- use_cases/               # Workflows grouped by entity
|   |       `-- user/                # User create, get, login, authenticate
|   |-- core/
|   |   |-- config/
|   |   |-- logging/
|   |   |-- middleware/
|   |   `-- handlers/
|   |-- domain/
|   |   |-- entities/
|   |   `-- value_objects/
|   |-- infrastructure/
|   |   |-- database/
|   |   |-- repositories/
|   |   `-- security/
|   `-- main.py
|-- docs/
|   `-- ARCHITECTURE_GUIDE.md        # Architecture and code guide
|-- environment/
|   |-- .env.development
|   |-- .env.uat
|   `-- .env.production
|-- tests/                           # Automated test suite
|-- .github/workflows/ci.yml         # CI pipeline
|-- alembic.ini
|-- docker-compose.yml
|-- Dockerfile
|-- pyproject.toml
|-- run.py
|-- README.md
`-- requirements.txt
```

## Requirements

- Python 3.12 or another version compatible with the dependencies
- PowerShell for the Windows commands shown below
- Git for source control

Runtime packages are declared in `requirements.txt`:

- `fastapi`: API framework
- `uvicorn[standard]`: ASGI development/runtime server
- `pydantic-settings`: typed environment configuration
- `ecs-logging`: Elastic Common Schema JSON formatter
- `SQLAlchemy`: asynchronous ORM and database session management
- `asyncpg`: asynchronous PostgreSQL driver

## Local setup

From the repository root:

```powershell
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install runtime and development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

If PowerShell execution policy prevents activation, the virtual environment can be used directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The `.venv/` directory is excluded from Git.

## Running the application

Use the environment-aware runner from the repository root:

```powershell
.\.venv\Scripts\python.exe run.py development
.\.venv\Scripts\python.exe run.py uat --no-reload
.\.venv\Scripts\python.exe run.py production --no-reload --host 0.0.0.0
```

The argument is required and must be `development`, `uat`, or `production`.
The runner sets `APP_ENV` before loading the application. Development binds to
`127.0.0.1:8000` with source reload enabled. UAT and production disable reload by
default unless you pass `--no-reload` explicitly for development.

The service is available at:

- API: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`
- Health (liveness): `http://127.0.0.1:8000/health/live`
- Health (readiness): `http://127.0.0.1:8000/health/ready`
- Swagger UI: `http://127.0.0.1:8000/docs` (development only)
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

You can still run Uvicorn directly when deployment tooling manages `APP_ENV`:

```powershell
$env:APP_ENV = "uat"
.\.venv\Scripts\python.exe -m uvicorn app.main:app
```

Valid selectors are `development`, `uat`, and `production`. An unsupported value prevents startup with a clear configuration error.

To remove the selector and return to the development default:

```powershell
Remove-Item Env:APP_ENV
```

`python run:development` is not supported because Python interprets
`run:development` as a filename. Use `python run.py development` instead.

## Configuration

Settings are defined in `app/core/config/settings.py`. The selected tracked file is loaded from `environment/.env.<APP_ENV>`.

Precedence is:

1. Process environment variables
2. The selected environment file

This allows deployment platforms to override tracked defaults without modifying repository files.

| Variable | Allowed/default values | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development`, `uat`, `production`; defaults to `development` | Selects the environment file |
| `APP_NAME` | `AML Backend` | Sets the FastAPI title and ECS service name |
| `DEBUG` | `true` or `false` | Controls FastAPI debug behavior |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Controls application and Uvicorn logging verbosity |
| `SECURITY_HEADERS_ENABLED` | `true` or `false` | Enables the security-header middleware |
| `HSTS_ENABLED` | `true` or `false` | Enables HTTP Strict Transport Security |
| `HSTS_MAX_AGE` | Non-negative integer | Sets the HSTS lifetime in seconds |
| `DB_HOST` | Non-empty hostname | PostgreSQL server hostname |
| `DB_PORT` | `1`–`65535`; defaults to `5432` | PostgreSQL server port |
| `DB_NAME` | Non-empty string | PostgreSQL database name |
| `DB_USER` | Non-empty string | PostgreSQL username |
| `DB_PASSWORD` | Required secret | PostgreSQL password supplied at runtime |
| `DB_POOL_SIZE` | Positive integer; defaults to `5` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | Non-negative integer; defaults to `10` | Extra connections beyond pool size |
| `DB_POOL_TIMEOUT` | Positive integer; defaults to `30` | Seconds to wait for a pool connection |
| `JWT_SECRET` | Required secret | Signing key for JWT access tokens |
| `JWT_ALGORITHM` | Defaults to `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | Positive integer; defaults to `60` | Access token lifetime |
| `CORS_ORIGINS` | Comma-separated origins | Allowed CORS origins (empty disables CORS middleware) |
| `TRUSTED_HOSTS` | Comma-separated hosts | Allowed Host headers in non-development environments |
| `RATE_LIMIT` | Defaults to `100/minute` | Default request rate limit |

Current defaults:

| Environment | Debug | Log level | Security headers | HSTS |
| --- | ---: | --- | ---: | ---: |
| Development | Enabled | `DEBUG` | Enabled | Disabled |
| UAT | Disabled | `INFO` | Enabled | Enabled |
| Production | Disabled | `INFO` | Enabled | Enabled |

### Configuration safety

The tracked files contain non-secret defaults only. Do not commit passwords, database credentials, tokens, private keys, or third-party API secrets. Supply secrets using deployment environment variables or an approved secret manager.

`Settings` constructs the encoded `postgresql+asyncpg` connection URL from the
separate database fields. The completed URL and password must never be logged.

HSTS must only be enabled when the environment is served exclusively over HTTPS. Browsers cache HSTS instructions, so it is intentionally disabled for local HTTP development.

## API endpoints

### Users

- `POST /api/v1/users/createUser` and `POST /api/v2/users` create an active, unverified user. Public registration always assigns the `user` role. Passwords must meet complexity requirements.
- `POST /api/v1/users/login` and `POST /api/v2/users/login` authenticate a user and return a JWT bearer token.
- `GET /api/v1/users/getUser/{user_id}` and `GET /api/v2/users/{user_id}` retrieve a user by UUID. Requires a valid bearer token.

### Health check

```http
GET /health
GET /health/live
GET /health/ready
```

`/health/live` confirms the process is running. `/health/ready` and `/health` also verify database connectivity and return HTTP `503` when PostgreSQL is unavailable.

## Logging and request correlation

The application writes newline-delimited ECS JSON to standard output. This output can be collected by Elastic Agent, Filebeat, a container platform, or another ELK-compatible log shipper.

Application and Uvicorn error logs include fields such as:

- `@timestamp`
- `log.level`
- `log.logger`
- `message`
- `service.name`
- `service.environment`
- `event.dataset`

HTTP request events additionally include:

- `http.request.method`
- `http.response.status_code`
- `url.path`
- `event.duration` in nanoseconds
- `event.outcome`
- `client.address`
- `trace.id`

### Request IDs

Clients may provide an `X-Request-ID` header:

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8000/health" `
  -Headers @{ "X-Request-ID" = "example-request-123" }
```

If no ID is supplied, the application generates one. Successful responses return the effective ID in `X-Request-ID`, and the same value appears as `trace.id` in the ECS request event.

The request logger deliberately excludes request and response bodies, query values, credentials, authorization headers, and other headers. Uvicorn's default access logger is disabled because its message includes raw query strings; the structured request middleware replaces it.

Unhandled request failures are logged at `ERROR` with exception information and are then re-raised for FastAPI's normal error handling.

## Security headers

When enabled, the application enforces these response headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

API responses also receive:

```http
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'
```

The CSP is omitted from `/docs`, `/redoc`, and `/openapi.json` so FastAPI's interactive documentation continues working.

When HSTS is enabled, responses receive:

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

The middleware overwrites conflicting downstream security headers so individual endpoints cannot weaken the application-wide policy.

This middleware does not implement authentication, authorization, CORS, CSRF protection, trusted-host validation, rate limiting, TLS termination, or secret management.

## Adding application features

Use a vertical workflow across the existing architecture rather than placing all logic in a router.

For example, system-user management could use:

```text
app/
|-- api/
|   |-- routers/
|   |   `-- user_router.py
|   `-- schemas/
|       `-- user_schema.py
|-- application/
|   |-- interfaces/
|   |   `-- user_repository.py
|   `-- use_cases/
|       `-- user/
|           |-- create_user.py
|           |-- get_user.py
|           |-- login.py
|           `-- authenticate_user.py
|-- domain/
|   `-- entities/
|       `-- user.py
`-- infrastructure/
    |-- database/
    |   `-- models/
    |       `-- user_model.py
    `-- repositories/
        `-- sql_user_repository.py
```

Recommended flow:

```text
UserRouter
    -> CreateUserUseCase
        -> User domain entity/rules
        -> UserRepository interface
            <- SQL repository implementation
```

Naming conventions:

- HTTP controller: `user_router.py`, exporting `router = APIRouter(...)`
- HTTP schemas: `user_schema.py`
- Application workflow: `create_user_use_case.py`, containing `CreateUserUseCase`
- Domain service: `risk_scoring_service.py`, containing `RiskScoringService`
- Repository contract: `user_repository.py`, containing `UserRepository`
- SQL adapter: `sql_user_repository.py`, containing `SqlUserRepository`
- Middleware: `<concern>_middleware.py`, containing `<Concern>Middleware`

Rules for new features:

1. Keep FastAPI request/response types in the API layer.
2. Keep orchestration in application use cases.
3. Keep business invariants in domain entities and domain services.
4. Define persistence contracts in application interfaces.
5. Implement those contracts in infrastructure.
6. Perform dependency injection at the API boundary.
7. Do not import FastAPI or SQLAlchemy into the domain layer.

For compliance-sensitive records, prefer explicit deactivation/soft deletion over destructive deletion when audit retention is required. Authorization and audit rules must be defined before exposing user-management endpoints.

## Testing and verification

An automated pytest suite covers use cases, API contracts, database helpers, middleware, and the environment runner.

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe app
```

### Database migrations

Apply migrations against the selected environment:

```powershell
$env:APP_ENV = "development"
.\.venv\Scripts\alembic.exe upgrade head
```

### Docker

```powershell
docker compose up --build
```

## Current scope and roadmap

Implemented:

- Clean Architecture package scaffold
- FastAPI application bootstrap with v1 and v2 APIs
- Development, UAT, and production configuration selection
- Typed settings validation with production secret checks
- ECS JSON console logging and request correlation
- Defensive response security headers, CORS, trusted hosts, and rate limiting
- JWT authentication and protected user retrieval
- User registration and login (create + get + login)
- Domain value objects (`Email`, `Username`) and `User.create()` factory
- Alembic migrations for `sm_user_t` and `sm_audit_event_t`
- Audit-event persistence for user create, login, and read actions
- DB-aware health checks (`/health`, `/health/live`, `/health/ready`)
- Async PostgreSQL engine with configurable connection pool
- Automated tests, ruff/mypy tooling, CI pipeline, and Docker packaging

Not yet implemented:

- AML transaction monitoring or risk scoring
- Customer KYC workflows
- User deactivation and role management APIs
- Sanctions or third-party API clients
- OpenTelemetry metrics and centralized audit log querying
- Infrastructure-as-code deployment beyond Docker Compose

These capabilities should be added incrementally while preserving the layer dependencies described above.
