from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from uuid import UUID
from loguru import logger

from ...db_util.core import DBSessionDep
from ...user_manage.models.user import User
from ...common.schemas.base import ResponseModel
from ...user_manage.service.security import check_permissions
from ...utils.schedule_utils import ScheduleUtils

from ..models.task import TaskSchedule
from ..schemas.task import TaskScheduleCreate, TaskScheduleResponse
from ..service.task import get_task_by_id_with_permission
from ..service.scheduler import (
    get_schedule_by_id,
    get_active_schedule_by_task_id,
    get_schedule_by_task_id,
    get_schedules_by_task_id,
    update_schedule_status,
    create_schedule,
    update_schedule_config,
)


router = APIRouter()
obj = 'Scheduler'  # 资源对象名称

@router.post("/")
async def create_task_schedule(
    schedule_data: TaskScheduleCreate,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """
    创建任务调度
    
    **参数:**
    - `schedule_data`: 包含调度配置的 `TaskScheduleCreate` 对象
    
    **返回:**
    - 包含成功消息和新创建调度ID的JSON响应
    """
    # 检查任务是否存在及权限
    task = await get_task_by_id_with_permission(db, schedule_data.task_id, str(user.id), user.is_admin)
    if not task:
        logger.warning(f"尝试为不存在的任务创建调度或无权限: {schedule_data.task_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权限访问"
        )
    # 检查是否已有调度（无论是否活跃）
    task_id_str = str(schedule_data.task_id)
    existing_schedule = await get_schedule_by_task_id(db, task_id_str)
    
    if existing_schedule:
        # 如果已有调度，则更新现有调度配置
        logger.info(f"任务 {task_id_str} 已有调度配置 {existing_schedule.id}，将更新配置")
        updated_schedule = await update_schedule_config(
            db, 
            existing_schedule, 
            schedule_data.schedule_type, 
            schedule_data.schedule_config
        )
        logger.info(f"成功更新调度配置 {updated_schedule.id} for task {task_id_str}")
        return ResponseModel(message="调度配置更新成功", data={
            "schedule_id": updated_schedule.id,
            "next_run_time": updated_schedule.next_run_time
        })
    else:
        # 如果没有调度，则创建新调度
        next_run_time = ScheduleUtils.calculate_next_run_time(schedule_data.schedule_type, schedule_data.schedule_config)
        logger.info(f"计算调度下次执行时间: {next_run_time}")
        db_schedule = await create_schedule(db, task_id_str, schedule_data.schedule_type, schedule_data.schedule_config, next_run_time)
        logger.info(f"成功创建调度 {db_schedule.id} for task {task_id_str}, 下次执行: {next_run_time}")
        return ResponseModel(message="调度创建成功", data={"schedule_id": db_schedule.id})


@router.get("/task/{task_id}")
async def get_task_schedules(
    task_id: UUID,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """
    获取任务的调度配置
    
    **参数:**
    - `task_id`: 任务ID
    
    **返回:**
    - 包含调度配置列表的JSON响应
    """
    # 检查任务是否存在及权限
    task = await get_task_by_id_with_permission(
        db, task_id, str(user.id), user.is_admin
    )
    if not task:
        logger.warning(f"尝试获取不存在任务的调度或无权限: {task_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权限访问"
        )
    # 获取任务的调度配置（每个任务只有一个调度）
    task_id_str = str(task_id)
    schedule = await get_schedule_by_task_id(db, task_id_str)
    if schedule:
        schedule_response = TaskScheduleResponse.model_validate(schedule)
        logger.info(f"获取任务 {task_id_str} 的调度配置: {schedule.id}")
        return ResponseModel(message="获取调度配置成功", data=[schedule_response])
    else:
        logger.info(f"任务 {task_id_str} 没有调度配置")
        return ResponseModel(message="获取调度配置成功", data=[])


@router.put("/{schedule_id}/toggle")
async def toggle_schedule(
    schedule_id: str,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """
    启用/禁用调度
    
    **参数:**
    - `schedule_id`: 调度ID
    
    **返回:**
    - 包含成功消息的JSON响应
    """
    # 获取调度
    schedule = await get_schedule_by_id(db, schedule_id)
    if not schedule:
        logger.warning(f"尝试切换不存在的调度: {schedule_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="调度不存在"
        )
    # 检查任务权限
    task = await get_task_by_id_with_permission(db, UUID(schedule.task_id), str(user.id), user.is_admin)
    if not task:
        logger.warning(f"用户 {user.id} 尝试修改不属于自己任务的调度 {schedule_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此调度"
        )
    # 切换状态
    new_status = not schedule.is_active
    next_run_time = None
    if new_status:
        # 重新计算下次执行时间
        next_run_time = ScheduleUtils.calculate_next_run_time(
            schedule.schedule_type,
            schedule.schedule_config
        )
        logger.info(f"启用调度 {schedule_id}，下次执行时间: {next_run_time}")
    else:
        logger.info(f"禁用调度 {schedule_id}")
    # 更新调度状态
    await update_schedule_status(db, schedule, new_status, next_run_time)
    
    status_text = "启用" if new_status else "禁用"
    return ResponseModel(message=f"调度{status_text}成功")

@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """
    删除调度
    
    **参数:**
    - `schedule_id`: 调度ID
    
    **返回:**
    - 包含成功消息的JSON响应
    """
    # 获取调度
    result = await db.execute(select(TaskSchedule).where(TaskSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        logger.warning(f"尝试删除不存在的调度: {schedule_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="调度不存在"
        )
    # 检查任务权限
    task = await get_task_by_id_with_permission(db, UUID(schedule.task_id), str(user.id), user.is_admin)
    if not task:
        logger.warning(f"用户 {user.id} 尝试删除不属于自己任务的调度 {schedule_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此调度"
        )
    # 删除调度
    await db.delete(schedule)
    await db.commit()
    logger.info(f"成功删除调度 {schedule_id}")
    return ResponseModel(message="调度删除成功")


@router.put("/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    schedule_data: TaskScheduleCreate,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """
    更新调度配置
    
    **参数:**
    - `schedule_id`: 调度ID
    - `schedule_data`: 包含新调度配置的 `TaskScheduleCreate` 对象
    
    **返回:**
    - 包含成功消息的JSON响应
    """
    # 获取调度
    schedule = await get_schedule_by_id(db, schedule_id)
    if not schedule:
        logger.warning(f"尝试更新不存在的调度: {schedule_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="调度不存在"
        )
    
    # 检查任务权限
    task = await get_task_by_id_with_permission(db, UUID(schedule.task_id), str(user.id), user.is_admin)
    if not task:
        logger.warning(f"用户 {user.id} 尝试修改不属于自己任务的调度 {schedule_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此调度"
        )
    
    # 更新调度配置
    updated_schedule = await update_schedule_config(
        db, 
        schedule, 
        schedule_data.schedule_type, 
        schedule_data.schedule_config
    )
    
    logger.info(f"成功更新调度配置 {schedule_id}")
    return ResponseModel(message="调度配置更新成功", data={
        "schedule_id": updated_schedule.id,
        "next_run_time": updated_schedule.next_run_time
    })

