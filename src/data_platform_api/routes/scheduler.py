from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from uuid import UUID

from ...db_util.core import DBSessionDep
from ...user_manage.models.user import User
from ...user_manage.routes.auth import get_current_active_user
from ...utils.scheduler import schedule_manager
from ...utils.schedule_utils import ScheduleUtils

from ..models.task import Task, TaskSchedule
from ..schemas.task import TaskScheduleCreate, TaskScheduleResponse
from ..schemas.common import Response


router = APIRouter()
_obj = 'Scheduler'

@router.post("/", response_model=Response)
async def create_schedule(
    schedule_data: TaskScheduleCreate,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """创建任务调度"""
    # 检查任务是否存在
    task_id_str = str(schedule_data.task_id)
    result = await db.execute(select(Task).where(Task.id == task_id_str))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能调度自己的任务
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权调度此任务"
        )
    
    # 检查是否已有活跃的调度
    existing_result = await db.execute(
        select(TaskSchedule).where(
            TaskSchedule.task_id == schedule_data.task_id,
            TaskSchedule.is_active == True
        )
    )
    existing_schedule = existing_result.scalar_one_or_none()
    
    if existing_schedule:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已有活跃的调度配置"
        )
    
    # 计算下次执行时间
    next_run_time = ScheduleUtils.calculate_next_run_time(schedule_data.schedule_type, schedule_data.schedule_config)
    
    # 创建调度
    db_schedule = TaskSchedule(
        task_id=schedule_data.task_id,
        schedule_type=schedule_data.schedule_type,
        schedule_config=schedule_data.schedule_config,
        next_run_time=next_run_time,
        is_active=True
    )
    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)
    
    # 添加到调度器
    schedule_manager.add_schedule(db_schedule)
    
    return Response(message="调度创建成功", data={"schedule_id": db_schedule.id})

@router.get("/task/{task_id}", response_model=Response)
async def get_task_schedules(
    task_id: UUID,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """获取任务的调度配置"""
    # 将UUID转换为字符串进行查询
    task_id_str = str(task_id)
    result = await db.execute(select(Task).where(Task.id == task_id_str))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能查看自己任务的调度
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务的调度配置"
        )
    
    result = await db.execute(
        select(TaskSchedule)
        .where(TaskSchedule.task_id == task_id_str)
        .order_by(desc(TaskSchedule.create_time))
    )
    schedules = result.scalars().all()
    
    schedule_list = [TaskScheduleResponse.model_validate(schedule) for schedule in schedules]
    
    return Response(data=schedule_list)

@router.put("/{schedule_id}/toggle", response_model=Response)
async def toggle_schedule(
    schedule_id: str,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """启用/禁用调度"""
    result = await db.execute(select(TaskSchedule).where(TaskSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="调度不存在"
        )
    
    # 检查权限
    task_result = await db.execute(select(Task).where(Task.id == schedule.task_id))
    task = task_result.scalar_one_or_none()
    
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此调度"
        )
    
    # 切换状态
    schedule.is_active = not schedule.is_active
    
    if schedule.is_active:
        # 重新计算下次执行时间
        schedule.next_run_time = ScheduleUtils.calculate_next_run_time(
            schedule.schedule_type,
            schedule.schedule_config
        )
        schedule_manager.add_schedule(schedule)
    else:
        schedule_manager.remove_schedule(schedule.id)
    
    await db.commit()
    
    status_text = "启用" if schedule.is_active else "禁用"
    return Response(message=f"调度{status_text}成功")

@router.delete("/{schedule_id}", response_model=Response)
async def delete_schedule(
    schedule_id: str,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """删除调度"""
    result = await db.execute(select(TaskSchedule).where(TaskSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="调度不存在"
        )
    
    # 检查权限
    task_result = await db.execute(select(Task).where(Task.id == schedule.task_id))
    task = task_result.scalar_one_or_none()
    
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此调度"
        )
    
    # 从调度器中移除
    schedule_manager.remove_schedule(schedule.id)
    
    # 删除调度
    await db.delete(schedule)
    await db.commit()
    
    return Response(message="调度删除成功")

