from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import text

from .celeryconfig import celery_app, redis_client
from .utils.task_progress_util import BaseTaskWithProgress
from .db import make_sync_session
from .db_tasks import (
    get_task_by_id,
    get_running_task_executions,
    update_task_status,
    update_task_execution_status,
    cleanup_old_executions,
    save_task_execution_to_db
)
from ..data_platform_api.models.task import TaskSchedule, Task, TaskExecution, ScheduleType
from ..utils.schedule_utils import ScheduleUtils


def process_scheduled_tasks_impl(
    self,
    namespace: str = "scheduler"
):
    """处理定时任务"""
    try:
        self.update_status(0, "PENDING", "开始处理定时任务", namespace=namespace)
        
        # 获取需要执行的任务
        scheduled_tasks = get_scheduled_tasks()
        
        if not scheduled_tasks:
            self.update_status(100, "SUCCESS", "没有需要执行的定时任务", namespace=namespace)
            return {"status": "success", "message": "没有需要执行的定时任务"}
        
        self.update_status(20, "RUNNING", f"找到 {len(scheduled_tasks)} 个定时任务", namespace=namespace)
        
        executed_count = 0
        for task_schedule in scheduled_tasks:
            try:
                # 执行任务
                if execute_scheduled_task(task_schedule):
                    executed_count += 1
                    logger.info(f"定时任务执行成功: {task_schedule.task_id}")
                else:
                    logger.error(f"定时任务执行失败: {task_schedule.task_id}")
                    
            except Exception as e:
                logger.error(f"执行定时任务时发生错误: {e}")
        
        self.update_status(100, "SUCCESS", f"定时任务处理完成，执行了 {executed_count} 个任务", namespace=namespace)
        
        return {
            "status": "success",
            "message": f"定时任务处理完成，执行了 {executed_count} 个任务",
            "executed_count": executed_count,
            "total_count": len(scheduled_tasks)
        }
        
    except Exception as e:
        logger.error(f"处理定时任务失败: {e}")
        self.update_status(0, "FAILURE", f"处理定时任务失败: {str(e)}", namespace=namespace)
        raise


def get_scheduled_tasks() -> List[TaskSchedule]:
    """获取需要执行的定时任务"""
    try:
        current_time = datetime.now()
        
        with make_sync_session() as session:
            # 查询需要执行的任务调度
            scheduled_tasks = session.query(TaskSchedule).filter(
                TaskSchedule.is_active == True,
                TaskSchedule.next_run_time <= current_time,
                TaskSchedule.is_delete == False
            ).all()
            
            return scheduled_tasks
            
    except Exception as e:
        logger.error(f"获取定时任务失败: {e}")
        return []


def execute_scheduled_task(task_schedule: TaskSchedule) -> bool:
    """执行单个定时任务"""
    try:
        # 获取任务信息 - 在session中立即提取所有属性
        with make_sync_session() as session:
            task = session.query(Task).filter(Task.id == task_schedule.task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_schedule.task_id}")
                return False
            
            # 立即提取所有需要的属性到普通Python对象
            task_id = str(task.id)
            task_name = task.task_name
            task_type = task.task_type
            base_url = task.base_url
            base_url_params = task.base_url_params if task.base_url_params else []
            need_user_login = task.need_user_login
            extract_config = task.extract_config if task.extract_config else {}
            description = task.description
            creator_id = task.creator_id
            
            # 检查任务是否已经在运行
            running_executions = get_running_task_executions()
            for execution in running_executions:
                if execution.task_id == task_schedule.task_id:
                    logger.info(f"任务 {task_schedule.task_id} 正在运行中，跳过")
                    return True
            
            # 【新增】检查连续失败记录，连续失败后自动禁用调度
            # 获取最近的3次执行记录（不限时间）
            recent_executions = session.query(TaskExecution).filter(
                TaskExecution.task_id == task_schedule.task_id
            ).order_by(TaskExecution.create_time.desc()).limit(3).all()
            
            # 如果最近3次执行都失败了，自动禁用调度
            if len(recent_executions) >= 3:
                all_failed = all(exec.status == "failed" for exec in recent_executions)
                if all_failed:
                    logger.error(
                        f"任务 {task_schedule.task_id} 连续失败3次，自动禁用调度。"
                        f"失败时间: {[str(e.end_time) for e in recent_executions]}"
                    )
                    
                    # 禁用调度
                    schedule = session.query(TaskSchedule).filter(
                        TaskSchedule.id == task_schedule.id
                    ).first()
                    if schedule:
                        schedule.is_active = False
                        session.commit()
                        logger.info(f"调度 {task_schedule.id} 已被自动禁用，请修复问题后手动重新启用")
                    
                    # 清理 Redis 中的退避计数（如果有）
                    try:
                        backoff_key = f"task_backoff:{task_schedule.task_id}"
                        redis_client.delete(backoff_key)
                    except:
                        pass
                    
                    return False  # 不执行新任务
            
            # 如果有成功执行，清除失败计数
            if recent_executions and recent_executions[0].status == "success":
                try:
                    backoff_key = f"task_backoff:{task_schedule.task_id}"
                    redis_client.delete(backoff_key)
                except:
                    pass
            
            # 创建任务执行记录
            execution_data = {
                "task_id": task_schedule.task_id,
                "executor_id": creator_id,  # 使用任务创建者作为执行者
                "execution_name": f"Scheduled execution for {task_name}",
                "status": "pending"
            }
            
            execution_id = save_task_execution_to_db(execution_data)
            if not execution_id:
                logger.error(f"创建任务执行记录失败: {task_schedule.task_id}")
                return False
            
            # 构建任务配置数据
            config_data = {
                "task_name": task_name,
                "task_type": task_type,
                "base_url": base_url,
                "base_url_params": base_url_params,
                "need_user_login": need_user_login,
                "extract_config": extract_config,
                "description": description,
            }
            logger.info(f"Celery Beat构建的config_data: {config_data}")
            
            # 异步执行任务 - 传递config_data
            celery_app.send_task(
                'execute_data_collection_task',
                args=[task_id, execution_id, config_data]
            )
        
        # 更新下次执行时间
        update_next_run_time(task_schedule)
        
        logger.info(f"定时任务已提交执行: {task_schedule.task_id}")
        return True
        
    except Exception as e:
        logger.error(f"执行定时任务失败: {e}")
        return False


def update_next_run_time(task_schedule: TaskSchedule) -> bool:
    """更新下次执行时间"""
    try:
        with make_sync_session() as session:
            schedule = session.query(TaskSchedule).filter(
                TaskSchedule.id == task_schedule.id
            ).first()
            
            if not schedule:
                return False
            
            # 使用 ScheduleUtils 计算下次执行时间
            config = schedule.schedule_config or {}
            next_time = ScheduleUtils.calculate_next_run_time(schedule.schedule_type, config)
            
            # 处理特殊调度类型
            if schedule.schedule_type == ScheduleType.SCHEDULED:
                # 一次性调度，执行后禁用
                schedule.is_active = False
                
            if next_time:
                schedule.next_run_time = next_time
                session.commit()
                logger.info(f"更新下次执行时间: {next_time}")
                return True
            
            return False
            
    except Exception as e:
        logger.error(f"更新下次执行时间失败: {e}")
        return False


def daily_cleanup_task_impl(
    self,
    days: int = 30,
    namespace: str = "cleanup"
):
    """清理旧数据"""
    try:
        self.update_status(0, "PENDING", "开始清理旧数据", namespace=namespace)
        
        # 清理旧的执行记录
        self.update_status(20, "RUNNING", "清理旧的执行记录", namespace=namespace)
        cleaned_executions = cleanup_old_executions(days)
        
        # 清理旧的任务调度记录
        self.update_status(50, "RUNNING", "清理旧的任务调度记录", namespace=namespace)
        cleaned_schedules = cleanup_old_schedules(days)
        
        # 清理 Redis 中的旧数据
        self.update_status(80, "RUNNING", "清理 Redis 中的旧数据", namespace=namespace)
        cleaned_redis = cleanup_old_redis_data(days)
        
        self.update_status(100, "SUCCESS", "旧数据清理完成", namespace=namespace)
        
        return {
            "status": "success",
            "message": "旧数据清理完成",
            "cleaned_executions": cleaned_executions,
            "cleaned_schedules": cleaned_schedules,
            "cleaned_redis_keys": cleaned_redis
        }
        
    except Exception as e:
        logger.error(f"清理旧数据失败: {e}")
        self.update_status(0, "FAILURE", f"清理旧数据失败: {str(e)}", namespace=namespace)
        raise


def cleanup_old_schedules(days: int) -> int:
    """清理旧的任务调度记录"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with make_sync_session() as session:
            count = session.query(TaskSchedule).filter(
                TaskSchedule.create_time < cutoff_date,
                TaskSchedule.is_active == False,
                TaskSchedule.is_delete == False
            ).update({"is_delete": True})
            
            session.commit()
            logger.info(f"清理了 {count} 个旧的任务调度记录")
            return count
            
    except Exception as e:
        logger.error(f"清理旧的任务调度记录失败: {e}")
        return 0


def cleanup_old_redis_data(days: int) -> int:
    """清理 Redis 中的旧数据"""
    try:
        # 清理过期的任务状态
        pattern = "*:status:*"
        keys = redis_client.keys(pattern)
        
        cleaned_count = 0
        for key in keys:
            try:
                # 检查键的 TTL
                ttl = redis_client.ttl(key)
                if ttl > 0 and ttl < (days * 24 * 3600):  # 如果 TTL 小于指定天数
                    redis_client.delete(key)
                    cleaned_count += 1
            except Exception as e:
                logger.warning(f"清理 Redis 键失败 {key}: {e}")
        
        logger.info(f"清理了 {cleaned_count} 个 Redis 键")
        return cleaned_count
        
    except Exception as e:
        logger.error(f"清理 Redis 数据失败: {e}")
        return 0


def system_health_check_task_impl(
    self,
    namespace: str = "health_check"
):
    """系统健康检查任务实现"""
    try:
        self.update_status(0, "PENDING", "开始系统健康检查", namespace=namespace)
        
        # 检查数据库连接
        try:
            with make_sync_session() as session:
                session.execute(text("SELECT 1"))
            db_status = "healthy"
            self.update_status(20, "PROGRESS", "数据库连接正常", namespace=namespace)
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
            logger.error(f"数据库健康检查失败: {e}")
            self.update_status(20, "PROGRESS", "数据库连接异常", namespace=namespace)
        
        # 检查Redis连接
        try:
            # 使用celeryconfig中配置的redis_client
            redis_client.ping()
            redis_status = "healthy"
            self.update_status(40, "PROGRESS", "Redis连接正常", namespace=namespace)
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"
            logger.error(f"Redis健康检查失败: {e}")
            self.update_status(40, "PROGRESS", "Redis连接异常", namespace=namespace)
        
        # 检查运行中的任务
        try:
            running_executions = get_running_task_executions()
            running_tasks_count = len(running_executions)
            self.update_status(60, "PROGRESS", f"运行中任务: {running_tasks_count}", namespace=namespace)
        except Exception as e:
            running_tasks_count = 0
            logger.error(f"获取运行中任务失败: {e}")
            self.update_status(60, "PROGRESS", "获取运行中任务失败", namespace=namespace)
        
        # 生成健康报告
        health_report = {
            "database": db_status,
            "redis": redis_status,
            "running_tasks": running_tasks_count,
            "timestamp": datetime.now().isoformat()
        }
        
        self.update_status(100, "SUCCESS", "系统健康检查完成", namespace=namespace)
        
        return {
            "status": "success",
            "message": "系统健康检查完成",
            "running_tasks": running_tasks_count,
            "health_report": health_report
        }
        
    except Exception as e:
        logger.error(f"系统健康检查失败: {e}")
        self.update_status(0, "FAILURE", f"系统健康检查失败: {str(e)}", namespace=namespace)
        raise
