from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from ..models.task import TaskType, TaskStatus, ExecutionStatus, ScheduleType
from ...common.schemas.base import PaginationModel


class UrlParam(BaseModel):
    param_name: str
    param_type: str  # list, range, value
    param_value: str


class ExtractField(BaseModel):
    field_name: str
    field_source_type: str  # string, list
    field_source_key: str
    field_desc: str
    field_name_in_db: str


class ExtractConfig(BaseModel):
    extract_method: str  # api, css
    listened_uri: str
    extract_dataset_idtf: str
    extract_fields: List[ExtractField]


class TaskBase(BaseModel):
    task_name: str
    task_type: TaskType
    base_url: Optional[str] = None
    base_url_params: Optional[List[UrlParam]] = None
    need_user_login: int = 0  # 0-否，1-是
    extract_config: Optional[List[ExtractConfig]] = None
    description: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    task_name: Optional[str] = None
    task_type: Optional[TaskType] = None
    base_url: Optional[str] = None
    base_url_params: Optional[List[UrlParam]] = None
    need_user_login: Optional[int] = None
    extract_config: Optional[List[ExtractConfig]] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None


class TaskResponse(TaskBase):
    id: str
    status: TaskStatus
    creator_id: str
    create_time: datetime
    update_time: datetime
    
    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        }
    }


class TaskExecutionResponse(BaseModel):
    id: str
    task_id: str
    executor_id: str
    execution_name: str
    status: ExecutionStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    docker_container_name: Optional[str] = None
    docker_container_id: Optional[str] = None
    docker_port: Optional[int] = None
    docker_access_url: Optional[str] = None  # 访问地址
    result_data: Optional[Dict[str, Any]] = None
    error_log: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ScheduleConfig(BaseModel):
    # 即时执行：{}
    # 指定时间：{"datetime": "2024-01-01 12:00:00"}
    # 周调度：{"days": [1, 3, 5], "time": "09:00:00"} # 1=周一
    # 月调度：{"dates": [1, 15], "time": "09:00:00"} # 每月1号和15号
    pass


class TaskScheduleCreate(BaseModel):
    task_id: UUID
    schedule_type: ScheduleType
    schedule_config: Dict[str, Any]


class TaskScheduleResponse(BaseModel):
    id: str
    task_id: str
    schedule_type: ScheduleType
    schedule_config: Dict[str, Any]
    is_active: bool
    next_run_time: Optional[datetime] = None
    create_time: datetime
    
    class Config:
        from_attributes = True


class TaskPagination(PaginationModel):
    """任务分页查询"""
    status: Optional[TaskStatus] = None
    task_name: Optional[str] = None
