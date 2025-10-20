from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, and_, update, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count
from loguru import logger
from datetime import datetime

from ..models.task import Task, TaskExecution, TaskStatus, ExecutionStatus, TaskSchedule, ScheduleType
from ..schemas.task import TaskPagination, TaskUpdate, TaskExecutionSummary
from .scheduler import create_schedule
from ...utils.schedule_utils import ScheduleUtils


async def create_task(db: AsyncSession, task: Task):
    """创建任务"""
    logger.info(f"准备创建任务 - base_url_params: {task.base_url_params}, extract_config: {task.extract_config}")
    db.add(task)
    await db.commit()
    await db.refresh(task)
    logger.info(f"任务创建完成 - ID: {task.id}, base_url_params: {task.base_url_params}, extract_config: {task.extract_config}")
    return task


async def get_task_by_id(db: AsyncSession, task_id: UUID, user_id: Optional[str] = None, is_admin: bool = False):
    """根据ID获取任务"""
    # 将UUID转换为字符串进行查询，因为数据库中存储的是字符串
    task_id_str = str(task_id)
    statement = select(Task).where(and_(Task.id == task_id_str, Task.is_delete == False))
    
    # 权限过滤：非管理员只能查看自己的任务
    if not is_admin and user_id:
        statement = statement.where(Task.creator_id == user_id)
    
    result = await db.execute(statement)
    return result.scalars().first()


async def get_task_by_name(db: AsyncSession, name: str):
    """根据名称获取任务"""
    statement = select(Task).where(and_(Task.task_name == name, Task.is_delete == False))
    result = await db.execute(statement)
    return result.scalars().first()


async def get_all_tasks(db: AsyncSession):
    """获取所有任务"""
    statement = select(Task).where(Task.is_delete == False)
    result = await db.execute(statement)
    return result.scalars().all()


async def get_page_tasks(db: AsyncSession, sort_bys: List[str], sort_orders: List[str], pagination: TaskPagination, user_id: Optional[str] = None, is_admin: bool = False):
    """分页获取任务列表"""
    stmt = select(Task).where(Task.is_delete == False)
    
    # 权限过滤：非管理员只能查看自己的任务
    if not is_admin and user_id:
        stmt = stmt.where(Task.creator_id == user_id)
    
    # 搜索条件
    if pagination.key_word:
        stmt = stmt.where(Task.task_name.contains(pagination.key_word))
    if pagination.status:
        stmt = stmt.where(Task.status == pagination.status)
    
    # 排序
    if sort_bys:
        stmt = stmt.order_by(*[getattr(Task, sort_field).asc() if sort_order == "asc" 
                            else getattr(Task, sort_field).desc()
                            for sort_field, sort_order in zip(sort_bys, sort_orders)])
    
    # 分页（将页码从1开始转换为从0开始）
    offset = (pagination.page - 1) * pagination.page_size
    stmt = stmt.offset(offset).limit(pagination.page_size)
    items = await db.execute(stmt)
    return items.scalars().all()


async def get_page_total(db: AsyncSession, pagination: TaskPagination, user_id: Optional[str] = None, is_admin: bool = False):
    """获取分页总数"""
    total_stmt = select(count(Task.id)).where(Task.is_delete == False)
    
    # 权限过滤：非管理员只能查看自己的任务
    if not is_admin and user_id:
        total_stmt = total_stmt.where(Task.creator_id == user_id)
    if pagination.key_word:
        total_stmt = total_stmt.where(Task.task_name.contains(pagination.key_word))
    if pagination.status:
        total_stmt = total_stmt.where(Task.status == pagination.status)
    total = await db.execute(total_stmt)
    return total.scalars().first()


async def update_task_by_id(db: AsyncSession, task_id: UUID, update_data: dict):
    """更新任务"""
    stmt = update(Task).where(and_(Task.id == task_id, Task.is_delete == False)).values(**update_data)
    await db.execute(stmt)
    await db.commit()


async def update_task_status(db: AsyncSession, task_id: UUID, status: TaskStatus):
    """更新任务状态"""
    task_id_str = str(task_id)
    stmt = update(Task).where(and_(Task.id == task_id_str, Task.is_delete == False)).values(status=status)
    await db.execute(stmt)
    await db.commit()


async def delete_task_by_id(db: AsyncSession, task_id: UUID):
    """软删除任务"""
    task_id_str = str(task_id)
    stmt = update(Task).where(Task.id == task_id_str).values(is_delete=True)
    await db.execute(stmt)
    await db.commit()


async def get_tasks_by_status(db: AsyncSession, status: TaskStatus):
    """根据状态获取任务列表"""
    statement = select(Task).where(and_(Task.status == status, Task.is_delete == False))
    result = await db.execute(statement)
    return result.scalars().all()


async def get_running_tasks_count(db: AsyncSession):
    """获取运行中任务数量"""
    statement = select(count(Task.id)).where(and_(Task.status == TaskStatus.RUNNING, Task.is_delete == False))
    result = await db.execute(statement)
    return result.scalars().first() or 0


# ==================== 任务执行相关操作 ====================

async def get_task_by_id_with_permission(db: AsyncSession, task_id: UUID, user_id: str, is_admin: bool = False):
    """根据ID获取任务（带权限检查）"""
    task_id_str = str(task_id)
    statement = select(Task).where(and_(Task.id == task_id_str, Task.is_delete == False))
    
    # 权限过滤：非管理员只能查看自己的任务
    if not is_admin:
        statement = statement.where(Task.creator_id == user_id)
    
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_running_execution_by_task_id(db: AsyncSession, task_id: str):
    """获取任务的正在执行记录"""
    statement = select(TaskExecution).where(
        TaskExecution.task_id == task_id,
        TaskExecution.status == ExecutionStatus.RUNNING
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def update_task_with_validation(db: AsyncSession, task_id: UUID, update_data: TaskUpdate, user_id: str, is_admin: bool = False):
    """更新任务（带权限和状态验证）"""
    # 获取任务
    task = await get_task_by_id_with_permission(db, task_id, user_id, is_admin)
    if not task:
        return None, "任务不存在或无权限访问"
    
    # 检查是否有正在执行的任务
    running_execution = await get_running_execution_by_task_id(db, str(task_id))
    if running_execution:
        return None, "任务正在执行中，无法修改"
    
    # 更新任务信息
    # 确保 update_data 是 Pydantic 模型实例
    if hasattr(update_data, 'model_dump'):
        update_dict = update_data.model_dump(exclude_unset=True)
    else:
        # 如果已经是字典，直接使用
        update_dict = update_data
    
    # 处理调度配置变更 - 简化逻辑：删除旧调度，创建新调度
    schedule_created = False
    if update_dict.get("trigger_method") == "auto" and task.trigger_method == "manual":
        # 从手动改为自动，必须提供调度配置
        if not update_dict.get("schedule_type") or not update_dict.get("schedule_config"):
            return None, "从手动改为自动任务时，必须提供schedule_type和schedule_config参数"
        
        # 创建调度配置
        schedule_type = update_dict.get("schedule_type")
        schedule_config = update_dict.get("schedule_config")
        next_run_time = ScheduleUtils.calculate_next_run_time(schedule_type, schedule_config)
        
        await create_schedule(
            db,
            str(task_id),
            schedule_type,
            schedule_config,
            next_run_time
        )
        schedule_created = True
        logger.info(f"任务 {task_id} 从手动改为自动，已创建调度配置")
    elif update_dict.get("trigger_method") == "manual" and task.trigger_method == "auto":
        # 从自动改为手动，删除所有调度
        schedule_stmt = select(TaskSchedule).where(
            and_(TaskSchedule.task_id == str(task_id), TaskSchedule.is_delete == False)
        )
        schedule_result = await db.execute(schedule_stmt)
        schedules = schedule_result.scalars().all()
        
        for schedule in schedules:
            schedule.is_delete = True
            logger.info(f"任务 {task_id} 从自动改为手动，已删除调度 {schedule.id}")
    elif task.trigger_method == "auto" and (update_dict.get("schedule_type") or update_dict.get("schedule_config")):
        # 自动任务更新调度配置：删除旧调度，创建新调度
        if not update_dict.get("schedule_type") or not update_dict.get("schedule_config"):
            return None, "更新自动任务调度配置时，必须提供schedule_type和schedule_config参数"
        
        # 删除所有旧调度
        schedule_stmt = select(TaskSchedule).where(
            and_(TaskSchedule.task_id == str(task_id), TaskSchedule.is_delete == False)
        )
        schedule_result = await db.execute(schedule_stmt)
        old_schedules = schedule_result.scalars().all()
        
        for schedule in old_schedules:
            schedule.is_delete = True
            logger.info(f"任务 {task_id} 更新调度配置，已删除旧调度 {schedule.id}")
        
        # 创建新调度
        schedule_type = update_dict.get("schedule_type")
        schedule_config = update_dict.get("schedule_config")
        next_run_time = ScheduleUtils.calculate_next_run_time(schedule_type, schedule_config)
        
        await create_schedule(
            db,
            str(task_id),
            schedule_type,
            schedule_config,
            next_run_time
        )
        schedule_created = True
        logger.info(f"任务 {task_id} 更新调度配置，已创建新调度")
    
    for field, value in update_dict.items():
        # 跳过调度配置字段，这些字段不存储在任务表中
        if field in ["schedule_type", "schedule_config"]:
            continue
            
        if field in ["base_url_params", "extract_config"] and value is not None:
            if field == "base_url_params":
                # 确保每个参数都是 Pydantic 模型实例
                if value and isinstance(value, list):
                    processed_params = []
                    for param in value:
                        if hasattr(param, 'model_dump'):
                            processed_params.append(param.model_dump())
                        else:
                            processed_params.append(param)
                    value = processed_params
            elif field == "extract_config" and value is not None:
                if hasattr(value, 'model_dump'):
                    value = value.model_dump()
        setattr(task, field, value)
    
    await db.commit()
    return task, "任务更新成功"


async def delete_task_with_validation(db: AsyncSession, task_id: UUID, user_id: str, is_admin: bool = False):
    """删除任务（带权限和状态验证）"""
    # 获取任务
    task = await get_task_by_id_with_permission(db, task_id, user_id, is_admin)
    if not task:
        return None, "任务不存在或无权限访问"
    
    # 检查是否有正在执行的任务
    running_execution = await get_running_execution_by_task_id(db, str(task_id))
    if running_execution:
        return None, "任务正在执行中，请先停止任务"
    
    # 软删除任务：设置 is_delete = True
    task.is_delete = True
    
    # 同时软删除相关的调度记录
    schedule_stmt = update(TaskSchedule).where(
        TaskSchedule.task_id == str(task_id)
    ).values(is_delete=True)
    await db.execute(schedule_stmt)
    
    await db.commit()
    logger.info(f"任务 {task_id} 及其调度记录已软删除")
    return task, "任务删除成功"


async def create_task_execution(db: AsyncSession, task_id: UUID, executor_id: str, execution_name: str):
    """创建任务执行记录"""
    db_execution = TaskExecution(
        task_id=str(task_id),
        executor_id=executor_id,
        execution_name=execution_name,
        status=ExecutionStatus.PENDING
    )
    db.add(db_execution)
    await db.commit()
    await db.refresh(db_execution)
    return db_execution


async def stop_task_execution(db: AsyncSession, task_id: UUID, user_id: str, is_admin: bool = False):
    """停止任务执行"""
    # 获取任务
    task = await get_task_by_id_with_permission(db, task_id, user_id, is_admin)
    if not task:
        return None, "任务不存在或无权限访问"
    
    # 查找正在执行的任务
    running_execution = await get_running_execution_by_task_id(db, str(task_id))
    if not running_execution:
        return None, "没有正在执行的任务，无法停止"
    
    # 更新执行状态
    running_execution.status = ExecutionStatus.CANCELLED
    running_execution.end_time = datetime.now()
    await db.commit()
    
    return running_execution, "任务停止成功"


async def get_task_executions_paginated(
    db: AsyncSession, 
    task_id: UUID, 
    page: int, 
    page_size: int, 
    status: Optional[ExecutionStatus] = None,
    user_id: str = None,
    is_admin: bool = False
):
    """分页获取任务执行记录"""
    # 构建查询条件
    stmt = select(TaskExecution).where(TaskExecution.task_id == str(task_id))
    
    # 状态筛选
    if status:
        stmt = stmt.where(TaskExecution.status == status)
    # 排序
    stmt = stmt.order_by(TaskExecution.create_time.desc())
    # 分页（将页码从1开始转换为从0开始）
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    executions_result = await db.execute(stmt)
    executions = executions_result.scalars().all()
    # 获取总数
    count_stmt = select(func.count(TaskExecution.id)).where(TaskExecution.task_id == str(task_id))
    if status:
        count_stmt = count_stmt.where(TaskExecution.status == status)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0
    
    return executions, total


async def get_task_status_info(db: AsyncSession, task_id: UUID, user_id: str, is_admin: bool = False):
    """获取任务详细状态信息"""
    # 获取任务
    task = await get_task_by_id_with_permission(db, task_id, user_id, is_admin)
    if not task:
        return None, "任务不存在或无权限访问"
    
    # 检查是否有正在执行的记录
    running_execution = await get_running_execution_by_task_id(db, str(task_id))
    
    # 构建详细状态信息
    status_info = {
        "task_id": str(task_id),
        "task_name": task.task_name,
        "status": task.status,
        "status_description": {
            "active": "已激活，可以执行",
            "paused": "已暂停，无法执行",
            "running": "正在执行中"
        }.get(task.status, "未知状态"),
        "can_execute": task.status == TaskStatus.ACTIVE and not running_execution,
        "can_activate": task.status in [TaskStatus.PAUSED],
        "can_deactivate": task.status == TaskStatus.ACTIVE and not running_execution,
        "can_stop": running_execution is not None,
        "running_execution": {
            "execution_id": str(running_execution.id),
            "execution_name": running_execution.execution_name,
            "start_time": running_execution.start_time,
            "container_name": running_execution.docker_container_name,
            "last_heartbeat": running_execution.last_heartbeat
        } if running_execution else None,
        "execution_summary": {
            "total_executions": 0,  # 可以通过 /executions 接口获取详细统计
            "success_count": 0,
            "failed_count": 0,
            "last_execution_time": None
        }
    }
    
    return status_info, "获取任务状态成功"


async def activate_task_with_validation(db: AsyncSession, task_id: UUID, user_id: str, is_admin: bool = False):
    """激活任务（带验证）"""
    # 获取任务
    task = await get_task_by_id_with_permission(db, task_id, user_id, is_admin)
    if not task:
        return None, "任务不存在或无权限访问"
    
    # 检查任务状态
    if task.status == TaskStatus.ACTIVE:
        return None, "任务已处于激活状态，无需重复激活"
    elif task.status == TaskStatus.RUNNING:
        return None, "任务正在执行中，无法激活。请先停止当前执行"
    
    # 更新任务状态为激活
    await update_task_status(db, task_id, TaskStatus.ACTIVE)
    
    # 重新获取更新后的任务对象
    updated_task = await get_task_by_id_with_permission(db, task_id, user_id, is_admin)
    return updated_task, "任务激活成功"


async def deactivate_task_with_validation(db: AsyncSession, task_id: UUID, user_id: str, is_admin: bool = False):
    """停用任务（带验证）"""
    # 获取任务
    task = await get_task_by_id_with_permission(db, task_id, user_id, is_admin)
    if not task:
        return None, "任务不存在或无权限访问"
    
    # 检查任务状态
    if task.status == TaskStatus.PAUSED:
        return None, "任务已处于暂停状态，无需重复停用"
    elif task.status == TaskStatus.RUNNING:
        return None, "任务正在执行中，无法停用。请先停止当前执行"
    elif task.status != TaskStatus.ACTIVE:
        return None, f"任务状态为 {task.status}，无法停用非激活状态的任务"
    
    # 更新任务状态为停用
    await update_task_status(db, task_id, TaskStatus.PAUSED)
    
    # 重新获取更新后的任务对象
    updated_task = await get_task_by_id_with_permission(db, task_id, user_id, is_admin)
    return updated_task, "任务已停用"


async def fix_stopped_tasks_status(db: AsyncSession):
    """修复数据库中的STOPPED状态任务"""
    try:
        await db.execute(text("UPDATE tasks SET status = 'paused' WHERE status = 'stopped' AND is_delete = 0"))
        await db.commit()
        return True, "已将STOPPED状态的任务更新为PAUSED状态"
    except Exception as e:
        await db.rollback()
        return False, f"修复STOPPED状态失败: {e}"


async def get_task_execution_summary(db: AsyncSession, task_id: str) -> TaskExecutionSummary:
    """获取任务执行统计信息"""
    try:
        # 获取总执行次数
        total_stmt = select(count(TaskExecution.id)).where(TaskExecution.task_id == task_id)
        total_result = await db.execute(total_stmt)
        total_executions = total_result.scalar() or 0
        
        # 获取成功次数
        success_stmt = select(count(TaskExecution.id)).where(
            and_(TaskExecution.task_id == task_id, TaskExecution.status == ExecutionStatus.SUCCESS)
        )
        success_result = await db.execute(success_stmt)
        success_count = success_result.scalar() or 0
        
        # 获取失败次数
        failed_stmt = select(count(TaskExecution.id)).where(
            and_(TaskExecution.task_id == task_id, TaskExecution.status == ExecutionStatus.FAILED)
        )
        failed_result = await db.execute(failed_stmt)
        failed_count = failed_result.scalar() or 0
        
        # 获取最后一次执行信息
        last_execution_stmt = select(TaskExecution).where(
            TaskExecution.task_id == task_id
        ).order_by(TaskExecution.create_time.desc()).limit(1)
        last_execution_result = await db.execute(last_execution_stmt)
        last_execution = last_execution_result.scalars().first()
        
        last_execution_status = last_execution.status if last_execution else None
        last_execution_time = last_execution.end_time if last_execution else None
        
        # 获取下次执行时间（仅自动任务）
        next_execution_time = None
        schedule_stmt = select(TaskSchedule).where(
            and_(TaskSchedule.task_id == task_id, TaskSchedule.is_delete == False)
        ).order_by(TaskSchedule.create_time.desc()).limit(1)
        schedule_result = await db.execute(schedule_stmt)
        schedule = schedule_result.scalars().first()
        if schedule and schedule.is_active:
            next_execution_time = schedule.next_run_time
        
        return TaskExecutionSummary(
            total_executions=total_executions,
            success_count=success_count,
            failed_count=failed_count,
            last_execution_status=last_execution_status,
            last_execution_time=last_execution_time,
            next_execution_time=next_execution_time
        )
        
    except Exception as e:
        logger.error(f"获取任务执行统计信息失败: {e}")
        return TaskExecutionSummary(
            total_executions=0,
            success_count=0,
            failed_count=0,
            last_execution_status=None,
            last_execution_time=None,
            next_execution_time=None
        )
