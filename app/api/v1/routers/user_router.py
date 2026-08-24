from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from starlette.responses import JSONResponse

from app.api.dependencies import get_create_user_use_case, get_get_user_use_case
from app.api.helpers import success_response
from app.api.schemas import ApiResponse
from app.api.v1.schemas import CreateUserRequest, UserResponse
from app.application.use_cases import CreateUserCommand, CreateUserUseCase, GetUserUseCase


router = APIRouter(prefix="/users", tags=["v1 Users"])


@router.post("/createUser", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    request: Request,
    use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
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


@router.get("/getUser/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(
    user_id: UUID,
    request: Request,
    use_case: Annotated[GetUserUseCase, Depends(get_get_user_use_case)],
) -> JSONResponse:
    user = await use_case.execute(user_id)
    return success_response(
        request,
        data=UserResponse.model_validate(user),
        message="User retrieved successfully",
    )
