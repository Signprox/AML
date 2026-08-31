from uuid import UUID

from fastapi import Request, status
from starlette.responses import JSONResponse

from app.api.helpers import success_response
from app.api.schemas import CreateUserRequest, LoginRequest, LoginResponse, UserResponse
from app.application.use_cases import (
    CreateUserCommand,
    CreateUserUseCase,
    GetUserUseCase,
    LoginCommand,
    LoginUseCase,
)
from app.domain.entities import User


async def handle_create_user(
    payload: CreateUserRequest,
    request: Request,
    use_case: CreateUserUseCase,
) -> JSONResponse:
    user = await use_case.execute(
        CreateUserCommand(
            username=payload.username,
            email=str(payload.email),
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    )
    return success_response(
        request,
        data=UserResponse.model_validate(user),
        message="User created successfully",
        status_code=status.HTTP_201_CREATED,
    )


async def handle_get_user(
    user_id: UUID,
    request: Request,
    use_case: GetUserUseCase,
    *,
    actor: User,
) -> JSONResponse:
    user = await use_case.execute(user_id, actor_id=actor.id)
    return success_response(
        request,
        data=UserResponse.model_validate(user),
        message="User retrieved successfully",
    )


async def handle_login(
    payload: LoginRequest,
    request: Request,
    use_case: LoginUseCase,
) -> JSONResponse:
    result = await use_case.execute(
        LoginCommand(username=payload.username, password=payload.password)
    )
    return success_response(
        request,
        data=LoginResponse(
            access_token=result.access_token,
            token_type=result.token_type,
        ),
        message="Login successful",
    )
