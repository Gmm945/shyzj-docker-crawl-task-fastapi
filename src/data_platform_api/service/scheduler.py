from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..models.task import TaskSchedule
from ...utils.schedule_utils import ScheduleUtils


async def get_schedule_by_id(db: AsyncSession, schedule_id: str) -> Optional[TaskSchedule]:
    """根据ID获取调度"""
    result = await db.execute(
        select(TaskSchedule).where(
            TaskSchedule.id == schedule_id,
            TaskSchedule.is_delete == False
        )
    )
    return result.scalar_one_or_none()


async def get_active_schedule_by_task_id(db: AsyncSession, task_id: str) -> Optional[TaskSchedule]:
    """获取任务的活跃调度配置"""
    result = await db.execute(
        select(TaskSchedule).where(
            TaskSchedule.task_id == task_id,
            TaskSchedule.is_active == True,
            TaskSchedule.is_delete == False
        )
    )
    return result.scalar_one_or_none()


async def get_schedule_by_task_id(db: AsyncSession, task_id: str) -> Optional[TaskSchedule]:
    """获取任务的调度配置（无论是否活跃）"""
    result = await db.execute(
        select(TaskSchedule).where(
            TaskSchedule.task_id == task_id,
            TaskSchedule.is_delete == False
        ).order_by(TaskSchedule.create_time.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def get_schedules_by_task_id(db: AsyncSession, task_id: str) -> List[TaskSchedule]:
    """获取任务的所有调度配置"""
    result = await db.execute(
        select(TaskSchedule)
        .where(
            TaskSchedule.task_id == task_id,
            TaskSchedule.is_delete == False
        )
        .order_by(desc(TaskSchedule.create_time))
    )
    return result.scalars().all()


async def create_schedule(
    db: AsyncSession,
    task_id: str,
    schedule_type: str,
    schedule_config: dict,
    next_run_time
) -> TaskSchedule:
    """创建调度配置"""
    db_schedule = TaskSchedule(
        task_id=task_id,
        schedule_type=schedule_type,
        schedule_config=schedule_config,
        next_run_time=next_run_time,
        is_active=True
    )
    db.add(db_schedule)
    await db.flush()  # 刷新到数据库但不提交事务
    logger.info(f"创建调度成功: {db_schedule.id}, 任务ID: {task_id}")
    return db_schedule


async def update_schedule_status(
    db: AsyncSession,
    schedule: TaskSchedule,
    is_active: bool,
    next_run_time=None
) -> TaskSchedule:
    """更新调度状态"""
    schedule.is_active = is_active
    if next_run_time is not None:
        schedule.next_run_time = next_run_time
    await db.commit()
    logger.info(f"更新调度状态: {schedule.id}, 激活状态: {is_active}")
    return schedule


async def delete_schedule(db: AsyncSession, schedule: TaskSchedule) -> None:
    """删除调度"""
    schedule_id = schedule.id
    # 软删除：设置 is_delete = True
    schedule.is_delete = True
    await db.commit()
    logger.info(f"调度已软删除: {schedule_id}")


async def get_all_active_schedules(db: AsyncSession) -> List[TaskSchedule]:
    """获取所有活跃的调度配置"""
    result = await db.execute(
        select(TaskSchedule)
        .where(
            TaskSchedule.is_active == True,
            TaskSchedule.is_delete == False
        )
        .order_by(TaskSchedule.next_run_time)
    )
    return result.scalars().all()


async def update_schedule_config(
    db: AsyncSession,
    schedule: TaskSchedule,
    schedule_type: str,
    schedule_config: dict
) -> TaskSchedule:
    """更新调度配置"""
    # 更新调度类型和配置
    schedule.schedule_type = schedule_type
    schedule.schedule_config = schedule_config
    
    # 重新计算下次执行时间
    next_run_time = ScheduleUtils.calculate_next_run_time(schedule_type, schedule_config)
    schedule.next_run_time = next_run_time
    
    await db.commit()  # 提交事务确保数据持久化
    logger.info(f"更新调度配置成功: {schedule.id}, 下次执行时间: {next_run_time}")
    return schedule

