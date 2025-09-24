"""
Worker 模块 - 异步任务处理
参照 AKS 项目结构，在 main.py 中定义所有 Celery 任务
"""
from typing import Any, Dict, Optional, List
from uuid import UUID
from loguru import logger

from .celeryconfig import celery_app
from .utils.task_progress_util import BaseTaskWithProgress

# 导入具体实现函数
from .data_collection_tasks import execute_data_collection_task_impl
from .docker_management_tasks import (
    stop_docker_container_impl,
    kill_docker_container_impl,
    get_container_status_impl,
    get_container_logs_impl,
    monitor_container,
    cleanup_container,
    check_heartbeat_timeout,
)
from .monitoring_tasks import (
    monitor_all_task_executions_impl,
    cleanup_task_resources_impl,
    health_check_impl,
    cleanup_old_data_impl,
    heartbeat_monitor_impl,
)
from .scheduler_tasks import (
    process_scheduled_tasks_impl,
    daily_cleanup_task_impl,
    system_health_check_task_impl,
)


# 数据采集任务
@celery_app.task(
    name="execute_data_collection_task",
    base=BaseTaskWithProgress,
    bind=True,
    queue="task_execution",
)
def execute_data_collection_task(
    self,
    task_id: str,
    execution_id: str,
    config_data: Optional[Dict[str, Any]] = None,
    namespace: str = "data_collection"
):
    """执行数据采集任务"""
    return execute_data_collection_task_impl(self, task_id, execution_id, config_data, namespace)


# 监控任务
@celery_app.task(
    name="monitor_task_execution",
    base=BaseTaskWithProgress,
    bind=True,
    queue="monitoring",
)
def monitor_task_execution(
    self,
    namespace: str = "monitoring"
):
    """监控所有任务执行状态"""
    return monitor_all_task_executions_impl(self, namespace)


@celery_app.task(
    name="cleanup_task_resources",
    base=BaseTaskWithProgress,
    bind=True,
    queue="cleanup",
)
def cleanup_task_resources(
    self,
    task_id: str = None,
    namespace: str = "cleanup"
):
    """清理任务资源"""
    return cleanup_task_resources_impl(self, task_id, namespace)


@celery_app.task(
    name="health_check_task",
    base=BaseTaskWithProgress,
    bind=True,
    queue="health_check",
)
def health_check_task(
    self,
    namespace: str = "health_check"
):
    """系统健康检查"""
    return health_check_impl(self, namespace)


@celery_app.task(
    name="cleanup_old_data",
    base=BaseTaskWithProgress,
    bind=True,
    queue="cleanup",
)
def cleanup_old_data(
    self,
    days: int = 30,
    namespace: str = "cleanup"
):
    """清理旧数据"""
    return cleanup_old_data_impl(self, days, namespace)


# Docker 管理任务
@celery_app.task(
    name="stop_docker_container",
    base=BaseTaskWithProgress,
    bind=True,
    queue="docker_management",
)
def stop_docker_container(
    self,
    container_id: str,
    namespace: str = "docker_management"
):
    """停止Docker容器"""
    return stop_docker_container_impl(self, container_id, namespace)


@celery_app.task(
    name="kill_docker_container",
    base=BaseTaskWithProgress,
    bind=True,
    queue="docker_management",
)
def kill_docker_container(
    self,
    container_id: str,
    namespace: str = "docker_management"
):
    """强制杀死Docker容器"""
    return kill_docker_container_impl(self, container_id, namespace)


@celery_app.task(
    name="get_container_status",
    base=BaseTaskWithProgress,
    bind=True,
    queue="docker_management",
)
def get_container_status(
    self,
    container_id: str,
    namespace: str = "docker_management"
):
    """获取容器状态"""
    return get_container_status_impl(self, container_id, namespace)


@celery_app.task(
    name="get_container_logs",
    base=BaseTaskWithProgress,
    bind=True,
    queue="docker_management",
)
def get_container_logs(
    self,
    container_id: str,
    lines: int = 100,
    namespace: str = "docker_management"
):
    """获取容器日志"""
    return get_container_logs_impl(self, container_id, lines, namespace)


# 调度任务
@celery_app.task(
    name="process_scheduled_tasks",
    base=BaseTaskWithProgress,
    bind=True,
    queue="scheduler",
)
def process_scheduled_tasks(
    self,
    namespace: str = "scheduler"
):
    """处理定时任务"""
    return process_scheduled_tasks_impl(self, namespace)


@celery_app.task(
    name="daily_cleanup_task",
    base=BaseTaskWithProgress,
    bind=True,
    queue="cleanup",
)
def daily_cleanup_task(
    self,
    namespace: str = "cleanup"
):
    """每日清理任务"""
    return daily_cleanup_task_impl(self, namespace)


@celery_app.task(
    name="system_health_check_task",
    base=BaseTaskWithProgress,
    bind=True,
    queue="health_check",
)
def system_health_check_task(
    self,
    namespace: str = "health_check"
):
    """系统健康检查任务"""
    return system_health_check_task_impl(self, namespace)


@celery_app.task(
    name="heartbeat_monitor_task",
    base=BaseTaskWithProgress,
    bind=True,
    queue="monitoring",
)
def heartbeat_monitor_task(
    self,
    namespace: str = "heartbeat_monitor"
):
    """心跳监控任务 - 检测任务超时和失联"""
    return heartbeat_monitor_impl(self, namespace)


# 非Celery任务的辅助函数
def monitor_container(container_id: str, execution_id: str):
    """监控容器状态（非Celery任务）"""
    return monitor_container(container_id, execution_id)


def cleanup_container(container_id: str):
    """清理容器（非Celery任务）"""
    return cleanup_container(container_id)


def check_heartbeat_timeout(execution_id: str, timeout_minutes: int = 30):
    """检查心跳超时（非Celery任务）"""
    return check_heartbeat_timeout(execution_id, timeout_minutes)