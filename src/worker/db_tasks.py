from uuid import UUID
from typing import List, Optional
from loguru import logger
from datetime import datetime, timedelta

from .db import make_sync_session
from ..data_platform_api.models.task import TaskExecution, Task, ExecutionStatus, TaskStatus
from ..user_manage.models.user import User


def save_task_execution_to_db(execution_data: dict) -> bool:
    """保存任务执行记录到数据库"""
    try:
        new_execution = TaskExecution(**execution_data)
        with make_sync_session() as session:
            session.add(new_execution)
            session.commit()
            logger.info("Task execution saved to database successfully")
            return True
    except Exception as e:
        logger.error(f"Failed to save task execution to database: {str(e)}")
        return False


def update_task_execution_status(execution_id: UUID, status: str, **kwargs) -> bool:
    """更新任务执行状态"""
    try:
        exec_id_str = str(execution_id)
        with make_sync_session() as session:
            execution = session.query(TaskExecution).filter(TaskExecution.id == exec_id_str).first()
            if execution:
                execution.status = status
                for key, value in kwargs.items():
                    if hasattr(execution, key):
                        setattr(execution, key, value)
                session.commit()
                logger.info(f"Task execution {execution_id} status updated to {status}")
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to update task execution status: {str(e)}")
        return False


def get_task_execution_by_id(execution_id: UUID) -> Optional[TaskExecution]:
    """根据ID获取任务执行记录"""
    try:
        exec_id_str = str(execution_id)
        with make_sync_session() as session:
            execution = session.query(TaskExecution).filter(TaskExecution.id == exec_id_str).first()
            return execution
    except Exception as e:
        logger.error(f"Failed to get task execution: {str(e)}")
        return None


def get_running_task_executions() -> List[TaskExecution]:
    """获取所有运行中的任务执行记录"""
    try:
        with make_sync_session() as session:
            executions = session.query(TaskExecution).filter(
                TaskExecution.status == ExecutionStatus.RUNNING
            ).all()
            return executions
    except Exception as e:
        logger.error(f"Failed to get running task executions: {str(e)}")
        return []


def cleanup_old_executions(days: int = 7) -> int:
    """清理旧的执行记录"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        with make_sync_session() as session:
            count = session.query(TaskExecution).filter(
                TaskExecution.create_time < cutoff_date,
                TaskExecution.status.in_(["success", "failed", "cancelled"])
            ).delete()
            session.commit()
            logger.info(f"Cleaned up {count} old task executions")
            return count
    except Exception as e:
        logger.error(f"Failed to cleanup old executions: {str(e)}")
        return 0


def get_task_by_id(task_id: str) -> Optional[Task]:
    """根据ID获取任务"""
    try:
        with make_sync_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            return task
    except Exception as e:
        logger.error(f"Failed to get task: {str(e)}")
        return None


def get_user_by_id(user_id: UUID) -> Optional[User]:
    """根据ID获取用户"""
    try:
        with make_sync_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            return user
    except Exception as e:
        logger.error(f"Failed to get user: {str(e)}")
        return None


def update_task_status(task_id: str, status: str) -> bool:
    """更新任务状态"""
    try:
        # 将字符串转换为枚举值
        if status == "active":
            task_status = TaskStatus.ACTIVE
        elif status == "paused":
            task_status = TaskStatus.PAUSED
        elif status == "running":
            task_status = TaskStatus.RUNNING
        else:
            logger.error(f"Invalid task status: {status}")
            return False
        
        with make_sync_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = task_status
                session.commit()
                logger.info(f"Task {task_id} status updated to {task_status.value}")
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to update task status: {str(e)}")
        return False


def update_task_execution_port(execution_id: UUID, port: int, container_id: str) -> bool:
    """更新任务执行的端口号和容器ID"""
    try:
        with make_sync_session() as session:
            # 将UUID转换为字符串进行查询
            execution_id_str = str(execution_id)
            execution = session.query(TaskExecution).filter(TaskExecution.id == execution_id_str).first()
            if execution:
                execution.docker_port = port
                execution.docker_container_id = container_id
                session.commit()
                logger.info(f"Execution {execution_id} updated with port {port} and container_id {container_id}")
                return True
            else:
                logger.warning(f"Execution {execution_id} not found")
                return False
    except Exception as e:
        logger.error(f"Failed to update execution port: {str(e)}")
        return False
