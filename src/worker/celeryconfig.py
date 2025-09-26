import os
from datetime import timedelta
from celery import Celery
from kombu import Exchange, Queue
import redis
from ..config.auth_config import settings
# 简化的调度配置
beat_schedule = {
    # 心跳监控任务 - 每2分钟执行一次
    'heartbeat-monitor': {
        'task': 'heartbeat_monitor_task',
        'schedule': 120.0,  # 2分钟
        'options': {'queue': 'monitoring'}
    },
    # 系统健康检查 - 每5分钟执行一次
    'system-health-check': {
        'task': 'system_health_check_task',
        'schedule': 300.0,  # 5分钟
        'options': {'queue': 'health_check'}
    },
    # 每日清理任务 - 每天凌晨2点执行
    'daily-cleanup': {
        'task': 'daily_cleanup_task',
        'schedule': 86400.0,  # 24小时
        'options': {'queue': 'cleanup'}
    },
}
timezone = settings.TIMEZONE or "Asia/Shanghai"

# Redis配置
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
    decode_responses=True,
)

# 创建Celery应用
celery_app = Celery("data_platform")

celery_app.conf.update(
    # Use Redis as the message broker
    broker_url=settings.celery_broker_url,
    # Use Redis as the result backend
    result_backend=settings.celery_result_backend,
    # Set the expiration time for task results
    result_expires=timedelta(days=2),
    # Set 4 worker threads, each thread can handle 2 tasks simultaneously
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=0,
    task_default_max_retries=0,   
    # Use JSON as the serialization method
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # broker_connection_retry_on_startup=False,
    worker_enable_remote_control=True,
    # if local sys is MAC must be open 
    # worker_pool='solo',
    worker_pool='prefork',
    timezone=timezone,
    enable_utc=False,
    beat_schedule=beat_schedule,
)

# 默认队列
celery_app.conf.task_default_queue = "default"

# 定义所有队列
celery_app.conf.task_queues = (
    Queue("default", Exchange("default"), routing_key="default"),
    Queue("task_execution", Exchange("task_execution"), routing_key="task_execution"),
    Queue("docker_management", Exchange("docker_management"), routing_key="docker_management"),
    Queue("monitoring", Exchange("monitoring"), routing_key="monitoring"),
    Queue("scheduler", Exchange("scheduler"), routing_key="scheduler"),
    Queue("cleanup", Exchange("cleanup"), routing_key="cleanup"),
    Queue("health_check", Exchange("health_check"), routing_key="health_check"),
)

celery_app.conf.task_routes = {
    "execute_data_collection_task": {"queue": "task_execution"},
    "monitor_task_execution": {"queue": "monitoring"},
    "heartbeat_monitor_task": {"queue": "monitoring"},
    "cleanup_task_resources": {"queue": "cleanup"},
    "health_check_task": {"queue": "health_check"},
    "cleanup_old_data": {"queue": "cleanup"},
    "stop_docker_container": {"queue": "docker_management"},
    "kill_docker_container": {"queue": "docker_management"},
    "get_container_status": {"queue": "docker_management"},
    "get_container_logs": {"queue": "docker_management"},
    "process_scheduled_tasks": {"queue": "scheduler"},
    "daily_cleanup_task": {"queue": "scheduler"},
    "system_health_check_task": {"queue": "scheduler"},
}

# 任务超时配置
celery_app.conf.task_time_limit = 28900
celery_app.conf.task_soft_time_limit = 28800
