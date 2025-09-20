from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count

from ..models.task import Task
from ..schemas.task import TaskPagination, TaskStatus


async def create_task(db: AsyncSession, task: Task):
    """创建任务"""
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_task_by_id(db: AsyncSession, task_id: UUID):
    """根据ID获取任务"""
    statement = select(Task).where(and_(Task.id == task_id, Task.is_delete == False))
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


async def get_page_tasks(db: AsyncSession, sort_bys: List[str], sort_orders: List[str], pagination: TaskPagination):
    """分页获取任务列表"""
    stmt = select(Task).where(Task.is_delete == False)
    
    # 搜索条件
    if pagination.key_word:
        stmt = stmt.where(Task.name.contains(pagination.key_word))
    if pagination.status:
        stmt = stmt.where(Task.status == pagination.status)
    
    # 排序
    if sort_bys:
        stmt = stmt.order_by(*[getattr(Task, sort_field).asc() if sort_order == "asc" 
                              else getattr(Task, sort_field).desc()
                              for sort_field, sort_order in zip(sort_bys, sort_orders)])
    
    # 分页
    stmt = stmt.offset(pagination.page * pagination.page_size).limit(pagination.page_size)
    items = await db.execute(stmt)
    return items.scalars().all()


async def get_page_total(db: AsyncSession, pagination: TaskPagination):
    """获取分页总数"""
    total_stmt = select(count(Task.id)).where(Task.is_delete == False)
    if pagination.key_word:
        total_stmt = total_stmt.where(Task.name.contains(pagination.key_word))
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
    stmt = update(Task).where(and_(Task.id == task_id, Task.is_delete == False)).values({Task.status: status})
    await db.execute(stmt)
    await db.commit()


async def delete_task_by_id(db: AsyncSession, task_id: UUID):
    """软删除任务"""
    stmt = update(Task).where(Task.id == task_id).values({Task.is_delete: True})
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
