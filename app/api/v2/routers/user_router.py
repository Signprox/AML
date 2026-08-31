from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from starlette.responses import JSONResponse

from app.api.dependencies import (
    get_create_user_use_case,
    get_current_user,
    get_get_user_use_case,
    get_login_use_case,
)
from app.api.handlers.user_handlers import handle_create_user, handle_get_user, handle_login
from app.api.schemas import (
    ApiResponse,
    CreateUserRequest,
    LoginRequest,
    LoginResponse,
    UserResponse,
)
from app.application.use_cases import CreateUserUseCase, GetUserUseCase, LoginUseCase
from app.domain.entities import User

router = APIRouter(prefix="/users", tags=["v2 Users"])


@router.post("", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    request: Request,
    use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
) -> JSONResponse:
    return await handle_create_user(payload, request, use_case)


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(
    payload: LoginRequest,
    request: Request,
    use_case: Annotated[LoginUseCase, Depends(get_login_use_case)],
) -> JSONResponse:
    return await handle_login(payload, request, use_case)


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(
    user_id: UUID,
    request: Request,
    use_case: Annotated[GetUserUseCase, Depends(get_get_user_use_case)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    return await handle_get_user(user_id, request, use_case, actor=current_user)
