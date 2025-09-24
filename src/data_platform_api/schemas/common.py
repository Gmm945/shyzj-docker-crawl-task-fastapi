from pydantic import BaseModel
from typing import Any, Optional, List, Generic, TypeVar
from datetime import datetime

T = TypeVar("T")

class Response(BaseModel):
    success: bool = True
    message: str = "操作成功"
    data: Optional[Any] = None
    

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    

class HeartbeatRequest(BaseModel):
    execution_id: str  # 改为字符串，支持UUID格式
    container_name: str
    status: Optional[str] = None
    progress: Optional[dict] = None
    timestamp: Optional[int] = None  # 客户端时间戳，用于网络延迟检测


class CompletionRequest(BaseModel):
    """任务完成通知请求"""
    execution_id: str
    container_name: str
    success: bool = True
    result_data: Optional[dict] = None
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    database: str
    redis: str
    scheduler: str
    error: Optional[str] = None

class SystemInfoResponse(BaseModel):
    """系统信息响应"""
    name: str
    version: str
    description: str
    debug: bool
    log_level: str
