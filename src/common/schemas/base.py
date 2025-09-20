from pydantic import BaseModel
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
    page: int = 0
    page_size: int = 10
    key_word: Optional[str] = None


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
