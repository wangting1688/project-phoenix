from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class PaginationParams(BaseModel):
    page: int = 1
    size: int = 20


class PaginationResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
