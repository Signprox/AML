# AML Backend

FastAPI foundation for an Anti-Money Laundering (AML) backend, organized with Clean Architecture and Domain-Driven Design (DDD) boundaries.

The repository currently provides the application scaffold and cross-cutting platform concerns: environment-aware configuration, Elastic Common Schema (ECS) logging, request correlation, security response headers, health monitoring, and interactive API documentation. AML business workflows, persistence models, database migrations, authentication, and external integrations are intentionally not implemented yet.

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

- `entities/`: domain entities and value objects
- `services/`: business services such as risk scoring or sanctions evaluation

### Application layer

Location: `app/application/`

Coordinates business workflows without knowing how HTTP, databases, or third-party services work.

- `use_cases/`: actions such as creating a system user or monitoring a transaction
- `interfaces/`: repository and external-service contracts required by use cases

### Infrastructure layer

Location: `app/infrastructure/`

Contains technical adapters for interfaces defined by the application layer.

- `database/`: database sessions, ORM models, and persistence configuration
- `repositories/`: concrete repository implementations

Database and repository implementations are currently placeholders.

### API layer

Location: `app/api/`

Provides FastAPI presentation concerns.

- `routers/`: HTTP controllers represented by `APIRouter` instances
- Future API schemas should live under `app/api/schemas/`
- Future dependency injection wiring should live in `app/api/dependencies.py`

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
|-- alembic/                         # Migration placeholder
|-- app/
|   |-- api/
|   |   `-- routers/                 # FastAPI controllers
|   |-- application/
|   |   |-- interfaces/              # Abstract repositories and gateways
|   |   `-- use_cases/               # Application workflow orchestration
|   |-- core/
|   |   |-- config/
|   |   |   `-- settings.py          # Typed environment configuration
|   |   |-- logging/
|   |   |   `-- config.py            # ECS console logging
|   |   `-- middleware/
|   |       |-- request_logging_middleware.py
|   |       `-- security_headers_middleware.py
|   |-- domain/
|   |   |-- entities/                # Pure domain models
|   |   `-- services/                # Pure business services
|   |-- infrastructure/
|   |   |-- database/                # Database adapters (placeholder)
|   |   `-- repositories/            # Repository implementations (placeholder)
|   `-- main.py                       # FastAPI application entry point
|-- environment/
|   |-- .env.development
|   |-- .env.uat
|   `-- .env.production
|-- .gitignore
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

## Local setup

From the repository root:

```powershell
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

If PowerShell execution policy prevents activation, the virtual environment can be used directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The `.venv/` directory is excluded from Git.

## Running the application

Development is the default environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The service is available at:

- API: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

Select another environment before starting the server:

```powershell
$env:APP_ENV = "uat"
.\.venv\Scripts\python.exe -m uvicorn app.main:app
```

Valid selectors are `development`, `uat`, and `production`. An unsupported value prevents startup with a clear configuration error.

To remove the selector and return to the development default:

```powershell
Remove-Item Env:APP_ENV
```

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

Current defaults:

| Environment | Debug | Log level | Security headers | HSTS |
| --- | ---: | --- | ---: | ---: |
| Development | Enabled | `DEBUG` | Enabled | Disabled |
| UAT | Disabled | `INFO` | Enabled | Enabled |
| Production | Disabled | `INFO` | Enabled | Enabled |

### Configuration safety

The tracked files contain non-secret defaults only. Do not commit passwords, database credentials, tokens, private keys, or third-party API secrets. Supply secrets using deployment environment variables or an approved secret manager.

HSTS must only be enabled when the environment is served exclusively over HTTPS. Browsers cache HSTS instructions, so it is intentionally disabled for local HTTP development.

## API endpoints

### Health check

```http
GET /health
```

Successful response:

```json
{
  "status": "healthy"
}
```

The endpoint returns HTTP `200` when the application process is available. It currently does not check a database or external dependency because those integrations have not been implemented.

### API documentation

FastAPI automatically provides Swagger UI, ReDoc, and an OpenAPI document. Documentation endpoints are currently enabled in all environments.

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
|       |-- create_user_use_case.py
|       `-- deactivate_user_use_case.py
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

No committed automated test suite exists yet. At minimum, run these checks after changes.

### Import and compilation check

```powershell
.\.venv\Scripts\python.exe -m compileall -q app
.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title)"
```

### Health smoke test

Start the application, then run:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/health"
```

### Header smoke test

```powershell
$response = Invoke-WebRequest "http://127.0.0.1:8000/health"
$response.StatusCode
$response.Headers["X-Request-ID"]
$response.Headers["X-Content-Type-Options"]
$response.Headers["Content-Security-Policy"]
```

Expected development behavior:

- HTTP status is `200`.
- `X-Request-ID` is present.
- `X-Content-Type-Options` is `nosniff`.
- API CSP is present.
- HSTS is absent.

Before merging production features, add automated tests for domain rules, application use cases, repository adapters, API contracts, environment validation, middleware headers, and sensitive-data exclusion from logs.

## Current scope and roadmap

Implemented:

- Clean Architecture package scaffold
- FastAPI application bootstrap
- Development, UAT, and production configuration selection
- Typed settings validation
- ECS JSON console logging
- Application startup and shutdown events
- Request timing and correlation IDs
- Defensive response security headers
- Health endpoint and API documentation

Not yet implemented:

- AML transaction monitoring or risk scoring
- Customer KYC workflows
- System-user CRUD or deactivation
- Authentication, roles, and permissions
- PostgreSQL and SQLAlchemy integration
- Alembic migration configuration
- Audit-event persistence
- Sanctions or third-party API clients
- CORS, trusted-host validation, rate limiting, and centralized Problem Details errors
- Docker or infrastructure-as-code deployment
- Automated tests and CI/CD pipeline

These capabilities should be added incrementally while preserving the layer dependencies described above.
