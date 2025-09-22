from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ...db_util.core import DBSessionDep, CacheManager
from ...db_util.db import get_async_session
from ...user_manage.models.user import User
from ..models.task import Task, TaskExecution, TaskSchedule, TaskStatus, ExecutionStatus
from ..schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskExecutionResponse, 
    TaskScheduleCreate, TaskScheduleResponse, TaskPagination
)
from ...common.schemas.base import ResponseModel
from ...user_manage.routes.auth import get_current_active_user
from ...worker.main import execute_data_collection_task, stop_docker_container
# 缓存命名空间常量
task_cache_namespace = 'task'
from ..service.task import (
    create_task,
    get_task_by_id,
    get_task_by_name,
    get_page_tasks,
    get_page_total,
    update_task_by_id,
    update_task_status,
    delete_task_by_id,
    get_tasks_by_status,
    get_running_tasks_count
)
from datetime import datetime

router = APIRouter()
_obj = 'Task'

@router.post("/add")
async def add_task(
    req_body: TaskCreate,
    db: DBSessionDep,
    cache: CacheManager,
    user: User = Depends(get_current_active_user)
):
    """
    创建新任务

    **参数:**
    - `req_body`: 包含任务详情的 `TaskCreate` 对象

    **返回:**
    - 包含成功消息和新创建任务ID的JSON响应
    """
    # 检查任务名是否重复
    existing_task = await get_task_by_name(db, req_body.task_name)
    if existing_task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务名称已存在"
        )
    
    # 创建任务（直接激活）
    db_task = Task(
        task_name=req_body.task_name,
        task_type=req_body.task_type,
        base_url=req_body.base_url,
        base_url_params=[param.model_dump() for param in req_body.base_url_params] if req_body.base_url_params else None,
        need_user_login=bool(req_body.need_user_login),
        extract_config=[config.model_dump() for config in req_body.extract_config] if req_body.extract_config else None,
        description=req_body.description,
        creator_id=user.id,
        status=TaskStatus.ACTIVE  # 直接创建为激活状态
    )
    
    new_task = await create_task(db, db_task)
    
    res = ResponseModel(message="任务创建成功", data={"task_id": new_task.id})
    return Response(content=res.model_dump_json())

@router.get("/list")
async def get_task_list(
    db: DBSessionDep,
    cache: CacheManager,
    sort_bys: Optional[List[str]] = Query(["create_time"]),
    sort_orders: Optional[List[str]] = Query(["desc"]),
    pagination: TaskPagination = Depends(),
    user: User = Depends(get_current_active_user)
):
    """
    获取任务列表。支持按状态筛选，支持按任务名称模糊搜索。

    **参数:**
    - `sort_bys`: 指定排序字段的可选字符串列表。默认为 `["create_time"]`
    - `sort_orders`: 指定每个字段排序顺序的可选字符串列表。默认为 `["desc"]`
    - `pagination`: 包含分页参数和筛选条件的 `TaskPagination` 对象

    **返回:**
    - 包含任务列表和分页信息的JSON响应
    """
    # 构建缓存键
    cache_key_parts = [
        str(user.id),
        str(pagination.page),
        str(pagination.page_size),
        str(pagination.status),
        str(pagination.task_name),
        ",".join(sort_bys),
        ",".join(sort_orders)
    ]
    
    # 尝试从缓存获取
    cached_result = await cache.get_cache(task_cache_namespace, cache_key_parts)
    if cached_result:
        return Response(content=cached_result)
    
    # 非管理员只能查看自己的任务
    if not user.is_admin:
        # 这里需要在service层添加用户权限过滤
        pass
    
    tasks = await get_page_tasks(db, sort_bys, sort_orders, pagination)
    total = await get_page_total(db, pagination)
    
    task_list = [TaskResponse.model_validate(task) for task in tasks]
    
    res = ResponseModel(message="获取任务列表成功", data={
        "items": task_list,
        "total": total,
        "page": pagination.page + 1,
        "size": pagination.page_size,
        "pages": (total + pagination.page_size - 1) // pagination.page_size
    })
    
    result_json = res.model_dump_json()
    
    # 缓存结果（5分钟）
    await cache.set_cache(task_cache_namespace, cache_key_parts, result_json, ttl=300)
    
    return Response(content=result_json)

@router.get("/{task_id}")
async def get_task(
    task_id: UUID,
    db: DBSessionDep,
    cache: CacheManager,
    user: User = Depends(get_current_active_user)
):
    """
    获取任务详情

    **参数:**
    - `task_id`: 任务ID

    **返回:**
    - 包含任务详情的JSON响应
    """
    # 构建缓存键
    cache_key_parts = [str(task_id), str(user.id)]
    
    # 尝试从缓存获取
    cached_result = await cache.get_cache(task_cache_namespace, cache_key_parts)
    if cached_result:
        return Response(content=cached_result)
    
    task = await get_task_by_id(db, task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能查看自己的任务
    if not user.is_admin and task.creator_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    res = ResponseModel(message="获取任务详情成功", data=TaskResponse.model_validate(task))
    result_json = res.model_dump_json()
    
    # 缓存结果（10分钟）
    await cache.set_cache(task_cache_namespace, cache_key_parts, result_json, ttl=600)
    
    return Response(content=result_json)

@router.put("/{task_id}")
async def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """更新任务"""
    # 将UUID转换为字符串进行查询
    task_id_str = str(task_id)
    result = await db.execute(select(Task).where(Task.id == task_id_str))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能修改自己的任务
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此任务"
        )
    
    # 检查是否有正在执行的任务
    running_result = await db.execute(
        select(TaskExecution).where(
            TaskExecution.task_id == task_id,
            TaskExecution.status == ExecutionStatus.RUNNING
        )
    )
    running_execution = running_result.scalar_one_or_none()
    
    if running_execution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务正在执行中，无法修改"
        )
    
    # 更新任务信息
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in ["base_url_params", "extract_config"] and value is not None:
            if field == "base_url_params":
                value = [param.model_dump() for param in value]
            elif field == "extract_config":
                value = [config.model_dump() for config in value]
        setattr(task, field, value)
    
    await db.commit()
    return ResponseModel(message="任务更新成功")

@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """删除任务"""
    # 将UUID转换为字符串进行查询
    task_id_str = str(task_id)
    result = await db.execute(select(Task).where(Task.id == task_id_str))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能删除自己的任务
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此任务"
        )
    
    # 检查是否有正在执行的任务
    running_result = await db.execute(
        select(TaskExecution).where(
            TaskExecution.task_id == task_id,
            TaskExecution.status == ExecutionStatus.RUNNING
        )
    )
    running_execution = running_result.scalar_one_or_none()
    
    if running_execution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务正在执行中，请先停止任务"
        )
    
    await db.delete(task)
    await db.commit()
    return ResponseModel(message="任务删除成功")

@router.post("/{task_id}/execute")
async def execute_task_now(
    task_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """立即执行任务"""
    # 将UUID转换为字符串进行查询
    task_id_str = str(task_id)
    result = await db.execute(select(Task).where(Task.id == task_id_str))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能执行自己的任务
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权执行此任务"
        )
    
    # 检查任务状态（允许草稿和激活状态执行）
    if task.status not in [TaskStatus.ACTIVE, TaskStatus.DRAFT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能执行草稿或已激活的任务"
        )
    
    # 检查是否已有正在执行的任务
    running_result = await db.execute(
        select(TaskExecution).where(
            TaskExecution.task_id == task_id,
            TaskExecution.status == ExecutionStatus.RUNNING
        )
    )
    running_execution = running_result.scalar_one_or_none()
    
    if running_execution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已在执行中"
        )
    
    # 创建执行记录
    timestamp = int(datetime.now().timestamp())
    execution_name = f"{timestamp}_{task.task_name}"
    
    db_execution = TaskExecution(
        task_id=task_id,
        executor_id=current_user.id,
        execution_name=execution_name,
        status=ExecutionStatus.PENDING
    )
    db.add(db_execution)
    await db.commit()
    await db.refresh(db_execution)
    
    # 提交到Celery执行
    execute_data_collection_task.delay(str(task.id), str(db_execution.id))
    
    return ResponseModel(message="任务已提交执行", data={"execution_id": db_execution.id})

@router.post("/{task_id}/stop")
async def stop_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """停止正在执行的任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能停止自己的任务
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权停止此任务"
        )
    
    # 查找正在执行的任务
    running_result = await db.execute(
        select(TaskExecution).where(
            TaskExecution.task_id == task_id,
            TaskExecution.status == ExecutionStatus.RUNNING
        )
    )
    running_execution = running_result.scalar_one_or_none()
    
    if not running_execution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有正在执行的任务"
        )
    
    # 停止Docker容器（通过Celery任务）
    if running_execution.docker_container_id:
        stop_docker_container.delay(running_execution.docker_container_id)
    
    # 更新执行状态
    running_execution.status = ExecutionStatus.CANCELLED
    running_execution.end_time = datetime.now()
    await db.commit()
    
    return ResponseModel(message="任务停止成功")

@router.get("/{task_id}/executions")
async def get_task_executions(
    task_id: int,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """获取任务执行记录"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能查看自己任务的执行记录
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务的执行记录"
        )
    
    # 获取执行记录
    executions_result = await db.execute(
        select(TaskExecution)
        .where(TaskExecution.task_id == task_id)
        .order_by(desc(TaskExecution.created_at))
        .offset(skip)
        .limit(limit)
    )
    executions = executions_result.scalars().all()
    
    # 获取总数
    count_result = await db.execute(
        select(TaskExecution).where(TaskExecution.task_id == task_id)
    )
    total = len(count_result.scalars().all())
    
    execution_list = [TaskExecutionResponse.model_validate(execution) for execution in executions]
    
    return ResponseModel(data={
        "items": execution_list,
        "total": total,
        "page": skip // limit + 1,
        "size": limit,
        "pages": (total + limit - 1) // limit
    })

@router.post("/{task_id}/activate")
async def activate_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """激活任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能激活自己的任务
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权激活此任务"
        )
    
    # 检查任务状态
    if task.status == TaskStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已激活"
        )
    
    # 更新任务状态为激活
    await update_task_status(db, task_id, TaskStatus.ACTIVE)
    
    return ResponseModel(message="任务激活成功")

@router.post("/{task_id}/deactivate")
async def deactivate_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """停用任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能停用自己的任务
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权停用此任务"
        )
    
    # 检查任务状态
    if task.status != TaskStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务未激活"
        )
    
    # 更新任务状态为停用
    await update_task_status(db, task_id, TaskStatus.PAUSED)
    
    return ResponseModel(message="任务已停用")
