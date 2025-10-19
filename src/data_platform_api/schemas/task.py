from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from ..models.task import TaskType, TaskStatus, ExecutionStatus, ScheduleType, TriggerMethod
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


class ExtractConfig(BaseModel):
    extract_method: str  # api, css
    listened_uri: str
    extract_dataset_idtf: str
    extract_fields: List[ExtractField]


class TableColumn(BaseModel):
    name: str
    type: str
    length: Optional[int] = None
    comment: str
    rel_field_name: str


class DatabaseConfig(BaseModel):
    db_type: str
    host: str
    port: int
    username: str
    password: str
    database_name: str
    table_name: str
    table_columns: List[TableColumn]


class TaskBase(BaseModel):
    task_name: str
    task_type: TaskType
    trigger_method: TriggerMethod = TriggerMethod.MANUAL
    base_url: Optional[str] = None
    base_url_params: Optional[List[UrlParam]] = None
    need_user_login: int = 0  # 0-否，1-是
    extract_config: Optional[ExtractConfig] = None
    description: Optional[str] = None


class TaskCreate(TaskBase):
    """创建任务的请求模型"""
    
    # 继承 TaskBase 的所有字段，并添加字段级别的验证和说明
    task_name: str = Field(..., min_length=1, max_length=100, description="任务名称，必填，1-100字符")
    task_type: TaskType = Field(..., description="任务类型，必填")
    trigger_method: TriggerMethod = Field(default=TriggerMethod.MANUAL, description="触发方式，manual-手动，auto-自动")
    base_url: Optional[str] = Field(None, max_length=500, description="基础URL，最大500字符")
    base_url_params: Optional[List[UrlParam]] = Field(default=None, description="URL参数列表")
    need_user_login: int = Field(default=0, ge=0, le=1, description="是否需要用户登录，0-否，1-是")
    extract_config: Optional[ExtractConfig] = Field(default=None, description="数据提取配置")
    description: Optional[str] = Field(None, max_length=500, description="任务描述，最大500字符")
    
    # 调度配置（当trigger_method为auto时必填）
    schedule_type: Optional[ScheduleType] = Field(None, description="调度类型，auto模式时必填")
    schedule_config: Optional[Dict[str, Any]] = Field(None, description="调度配置，auto模式时必填")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_name": "示例手动任务",
                    "task_type": "api",
                    "trigger_method": "manual",
                    "base_url": "https://api.example.com/data",
                    "base_url_params": [],
                    "need_user_login": 0,
                    "extract_config": {
                        "extract_method": "api",
                        "listened_uri": "/data",
                        "extract_dataset_idtf": "api_data",
                        "extract_fields": []
                    },
                    "description": "这是一个手动执行的API数据采集任务"
                },
                {
                    "task_name": "示例自动任务",
                    "task_type": "docker-crawl",
                    "trigger_method": "auto",
                    "base_url": "https://example.com",
                    "description": "这是一个自动执行的爬虫任务",
                    "schedule_type": "hourly",
                    "schedule_config": {
                        "interval": 2
                    }
                }
            ]
        }
    }


class TaskUpdate(BaseModel):
    task_name: Optional[str] = None
    task_type: Optional[TaskType] = None
    trigger_method: Optional[TriggerMethod] = None
    base_url: Optional[str] = None
    base_url_params: Optional[List[UrlParam]] = None
    need_user_login: Optional[int] = None
    extract_config: Optional[ExtractConfig] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    
    # 调度配置（当trigger_method从manual改为auto时必填）
    schedule_type: Optional[ScheduleType] = Field(None, description="调度类型，从手动改为自动时必填")
    schedule_config: Optional[Dict[str, Any]] = Field(None, description="调度配置，从手动改为自动时必填")


class TaskExecutionSummary(BaseModel):
    """任务执行统计信息"""
    total_executions: int = Field(description="总执行次数")
    success_count: int = Field(description="成功次数")
    failed_count: int = Field(description="失败次数")
    last_execution_status: Optional[str] = Field(None, description="最后一次执行状态")
    last_execution_time: Optional[datetime] = Field(None, description="最后一次执行时间")
    next_execution_time: Optional[datetime] = Field(None, description="下次执行时间（仅自动任务）")


class TaskResponse(TaskBase):
    id: str
    status: TaskStatus
    creator_id: str
    create_time: datetime
    update_time: datetime
    execution_summary: Optional[TaskExecutionSummary] = Field(None, description="执行统计信息")
    
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


class ImmediateScheduleConfig(BaseModel):
    """即时执行配置 - 空配置"""
    pass


class DatetimeScheduleConfig(BaseModel):
    """指定时间执行配置"""
    datetime: str = Field(..., description="执行时间，格式: YYYY-MM-DD HH:MM:SS")


class WeeklyScheduleConfig(BaseModel):
    """周调度配置"""
    days: List[int] = Field(..., description="星期几执行，1=周一, 7=周日", min_items=1)
    time: str = Field(..., description="执行时间，格式: HH:MM:SS")


class MonthlyScheduleConfig(BaseModel):
    """月调度配置"""
    dates: List[int] = Field(..., description="每月几号执行，1-31", min_items=1)
    time: str = Field(..., description="执行时间，格式: HH:MM:SS")


class DailyScheduleConfig(BaseModel):
    """日调度配置"""
    time: str = Field(..., description="每天执行时间，格式: HH:MM:SS")


class IntervalScheduleConfig(BaseModel):
    """间隔调度配置"""
    interval: int = Field(..., description="间隔时间（秒）", gt=0)


class CronScheduleConfig(BaseModel):
    """Cron表达式调度配置"""
    cron_expression: str = Field(..., description="Cron表达式，如: 0 0 * * *")


class TaskScheduleCreate(BaseModel):
    task_id: UUID
    schedule_type: ScheduleType
    schedule_config: Dict[str, Any]


class TaskScheduleUpdate(BaseModel):
    """调度更新请求模型（不包含task_id）"""
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
    status: Optional[TaskStatus] = Field(None, description="任务状态筛选")
