import os
from datetime import timedelta
from celery import Celery
from kombu import Exchange, Queue
import redis
from ..config.auth_config import settings
# Celery Beat 定时任务配置
from celery.schedules import crontab

beat_schedule = {
    # ========== 核心调度任务 ==========
    # 处理定时任务 - 每分钟执行一次（核心功能）
    'process-scheduled-tasks': {
        'task': 'process_scheduled_tasks',
        'schedule': crontab(minute='*'),  # 每分钟执行
        'options': {'queue': 'scheduler'}
    },
    
    # ========== 监控任务 ==========
    # 心跳监控任务 - 每2分钟执行一次
    'heartbeat-monitor': {
        'task': 'heartbeat_monitor_task',
        'schedule': timedelta(seconds=120),  # 2分钟
        'options': {'queue': 'monitoring'}
    },
    
    # 监控任务执行 - 每30秒执行一次
    'monitor-task-execution': {
        'task': 'monitor_task_execution',
        'schedule': timedelta(seconds=30),  # 每30秒执行
        'options': {'queue': 'monitoring'}
    },
    
    # ========== 健康检查任务 ==========
    # 系统健康检查 - 每5分钟执行一次
    'system-health-check': {
        'task': 'system_health_check_task',
        'schedule': crontab(minute='*/5'),  # 每5分钟执行
        'options': {'queue': 'health_check'}
    },
    
    # ========== 清理任务 ==========
    # 清理旧数据 - 每天凌晨2点执行
    'cleanup-old-data': {
        'task': 'cleanup_old_data',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点
        'options': {'queue': 'cleanup'}
    },
    
    # 清理任务资源 - 每小时执行一次
    'cleanup-task-resources': {
        'task': 'cleanup_task_resources',
        'schedule': crontab(minute=0),  # 每小时执行
        'options': {'queue': 'cleanup'}
    },
    
    # 每日清理任务 - 每天凌晨3点执行
    'daily-cleanup': {
        'task': 'daily_cleanup_task',
        'schedule': crontab(hour=3, minute=0),  # 每天凌晨3点
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
