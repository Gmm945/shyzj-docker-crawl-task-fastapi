from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID


class ResponseModel(BaseModel):
    """统一响应模型"""
    message: Optional[str] = "Success"
    data: Optional[Any] = None

    model_config = {
        "json_encoders": {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat(),
        }
    }


class PaginationModel(BaseModel):
    """分页基础模型"""
    page: int = Field(1, ge=1, description="页码，从1开始")
    page_size: int = Field(10, ge=1, le=100, description="每页大小")
    key_word: Optional[str] = Field(None, description="关键词搜索")


class BaseEntityModel(BaseModel):
    """基础实体模型"""
    id: UUID
    create_time: datetime
    update_time: datetime

    model_config = {
        "json_encoders": {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat(),
        }
    }
