from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum, JSON, Integer
from .base import BaseModel
from datetime import datetime
import enum


class TaskType(str, enum.Enum):
    DOCKER_CRAWL = "docker-crawl"
    API = "api"
    DATABASE = "database"


class TaskStatus(str, enum.Enum):
    ACTIVE = "active" 
    PAUSED = "paused"
    RUNNING = "running"


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleType(str, enum.Enum):
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Task(BaseModel):
    __tablename__ = "tasks"
    __table_args__ = {'extend_existing': True}
    
    task_name = Column(String(200), nullable=False, comment="任务名称")
    task_type = Column(Enum(TaskType), nullable=False, comment="任务类型")
    status = Column(Enum(TaskStatus), default=TaskStatus.ACTIVE, comment="任务状态")
    
    # 爬虫配置
    base_url = Column(Text, nullable=True, comment="基础URL")
    base_url_params = Column(JSON, nullable=True, comment="URL参数")
    need_user_login = Column(Boolean, default=False, comment="是否需要用户登录")
    extract_config = Column(JSON, nullable=True, comment="提取配置")
    
    # 创建者
    creator_id = Column(String(36), nullable=False, comment="创建者ID")
    
    # 描述
    description = Column(Text, nullable=True, comment="任务描述")


class TaskExecution(BaseModel):
    __tablename__ = "task_executions"
    __table_args__ = {'extend_existing': True}
    
    task_id = Column(String(36), nullable=False, comment="任务ID")
    executor_id = Column(String(36), nullable=False, comment="执行者ID")
    
    # 执行信息
    execution_name = Column(String(255), nullable=False, comment="执行名称")
    status = Column(Enum(ExecutionStatus), default=ExecutionStatus.PENDING, comment="执行状态")
    
    # 执行时间
    start_time = Column(DateTime, nullable=True, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    
    # Docker信息
    docker_container_id = Column(String(64), nullable=True, comment="Docker容器ID")
    docker_config_path = Column(String(500), nullable=True, comment="Docker配置路径")
    docker_port = Column(Integer, nullable=True, comment="Docker容器端口号")
    
    # 结果和日志
    result_data = Column(JSON, nullable=True, comment="结果数据")
    error_log = Column(Text, nullable=True, comment="错误日志")
    
    # 心跳检测
    last_heartbeat = Column(DateTime, nullable=True, comment="最后心跳时间")

    # 兼容字段：提供 created_at 作为 create_time 的别名，避免接口/排序冲突
    @property
    def created_at(self):
        return self.create_time


class TaskSchedule(BaseModel):
    __tablename__ = "task_schedules"
    __table_args__ = {'extend_existing': True}
    
    task_id = Column(String(36), nullable=False, comment="任务ID")
    
    # 调度类型和配置
    schedule_type = Column(Enum(ScheduleType), nullable=False, comment="调度类型")
    schedule_config = Column(JSON, nullable=True, comment="调度配置")
    
    # 是否启用
    is_active = Column(Boolean, default=True, comment="是否启用")
    
    # 下次执行时间
    next_run_time = Column(DateTime, nullable=True, comment="下次执行时间")
