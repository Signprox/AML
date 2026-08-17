from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


ResponseData = TypeVar("ResponseData")


class PaginationMeta(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ResponseMeta(BaseModel):
    request_id: str
    pagination: PaginationMeta | None = None


class ApiError(BaseModel):
    code: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ApiResponse(BaseModel, Generic[ResponseData]):
    success: bool
    message: str
    data: ResponseData | None = None
    error: ApiError | None = None
    meta: ResponseMeta
