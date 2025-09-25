from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

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
    
    # 处理URL参数
    base_url_params_data = None
    if req_body.base_url_params:
        base_url_params_data = [param.model_dump() for param in req_body.base_url_params]
        logger.info(f"处理base_url_params: {len(base_url_params_data)} 个参数")
    
    # 处理提取配置
    extract_config_data = None
    if req_body.extract_config:
        extract_config_data = req_body.extract_config.model_dump()
        logger.info(f"处理extract_config: 已处理")

    # 创建任务（直接激活）
    db_task = Task(
        task_name=req_body.task_name,
        task_type=req_body.task_type,
        base_url=req_body.base_url,
        base_url_params=base_url_params_data,
        need_user_login=bool(req_body.need_user_login),
        extract_config=extract_config_data,
        description=req_body.description,
        creator_id=user.id,
        status=TaskStatus.ACTIVE  # 直接创建为激活状态
    )
    
    logger.info(f"创建任务对象 - base_url_params: {db_task.base_url_params}, extract_config: {db_task.extract_config}")
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
    
    try:
        # 调用service层函数，传入用户权限信息
        tasks = await get_page_tasks(db, sort_bys, sort_orders, pagination, str(user.id), user.is_admin)
        total = await get_page_total(db, pagination, str(user.id), user.is_admin)
    except Exception as e:
        if "'STOPPED' is not among the defined enum values" in str(e):
            logger.warning("检测到数据库中存在STOPPED状态的任务，尝试修复...")
            # 临时修复：将STOPPED状态的任务改为PAUSED
            try:
                from sqlalchemy import text
                await db.execute(text("UPDATE tasks SET status = 'paused' WHERE status = 'stopped' AND is_delete = 0"))
                await db.commit()
                logger.info("已将STOPPED状态的任务更新为PAUSED状态")
                # 重新查询
                tasks = await get_page_tasks(db, sort_bys, sort_orders, pagination, str(user.id), user.is_admin)
                total = await get_page_total(db, pagination, str(user.id), user.is_admin)
            except Exception as fix_error:
                logger.error(f"修复STOPPED状态失败: {fix_error}")
                raise e
        else:
            raise e
    
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
    
    # 调用service层函数，传入用户权限信息
    task = await get_task_by_id(db, task_id, str(user.id), user.is_admin)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权限访问"
        )
    
    # 获取任务数据并添加访问地址信息
    task_data = TaskResponse.model_validate(task)
    
    # 如果有正在运行的执行，添加访问地址
    if hasattr(task_data, 'running_execution') and task_data.running_execution:
        execution = task_data.running_execution
        if execution.docker_port:
            from ...config.auth_config import settings
            docker_host = settings.DOCKER_HOST_IP
            execution.docker_access_url = f"http://{docker_host}:{execution.docker_port}"
    
    res = ResponseModel(message="获取任务详情成功", data=task_data)
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
            TaskExecution.task_id == str(task_id),
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
            elif field == "extract_config" and value is not None:
                value = value.model_dump()

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
            TaskExecution.task_id == str(task_id),
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
    
    # 检查任务状态并给出具体提示
    if task.status == TaskStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已暂停，请先激活任务后再执行"
        )
    elif task.status == TaskStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务正在执行中，请等待完成或先停止当前执行"
        )
    elif task.status != TaskStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，只能执行已激活的任务"
        )
    
    # 检查是否已有正在执行的任务
    running_result = await db.execute(
        select(TaskExecution).where(
            TaskExecution.task_id == str(task_id),
            TaskExecution.status == ExecutionStatus.RUNNING
        )
    )
    running_execution = running_result.scalar_one_or_none()
    
    if running_execution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已在执行中"
        )
    
    # 创建执行记录（避免包含非常规字符，使用固定前缀+时间戳+任务ID片段）
    timestamp = int(datetime.now().timestamp())
    execution_name = f"exec_{timestamp}_{str(task.id)[:8]}"
    
    db_execution = TaskExecution(
        task_id=str(task_id),
        executor_id=current_user.id,
        execution_name=execution_name,
        status=ExecutionStatus.PENDING
    )
    db.add(db_execution)
    await db.commit()
    await db.refresh(db_execution)
    
    # 构建任务配置数据
    config_data = {
        "task_name": task.task_name,
        "task_type": task.task_type,
        "base_url": task.base_url,
        "base_url_params": task.base_url_params,
        "need_user_login": task.need_user_login,
        "extract_config": task.extract_config,
        "description": task.description,
    }
    
    # 提交到Celery执行
    execute_data_collection_task.delay(str(task.id), str(db_execution.id), config_data)
    
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
            detail="没有正在执行的任务，无法停止"
        )
    
    # 停止Docker容器（通过Celery任务）
    if running_execution.docker_container_name:
        stop_docker_container.delay(running_execution.docker_container_name)
    
    # 更新执行状态
    running_execution.status = ExecutionStatus.CANCELLED
    running_execution.end_time = datetime.now()
    await db.commit()
    
    return ResponseModel(message="任务停止成功")

@router.get("/{task_id}/executions")
async def get_task_executions(
    task_id: UUID,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """获取任务执行记录"""
    result = await db.execute(select(Task).where(Task.id == str(task_id)))
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
        .where(TaskExecution.task_id == str(task_id))
        .order_by(desc(TaskExecution.create_time))
        .offset(skip)
        .limit(limit)
    )
    executions = executions_result.scalars().all()
    
    # 获取总数
    count_result = await db.execute(
        select(TaskExecution).where(TaskExecution.task_id == str(task_id))
    )
    total = len(count_result.scalars().all())
    
    # 为每个执行记录添加访问地址
    execution_list = []
    for execution in executions:
        execution_data = TaskExecutionResponse.model_validate(execution)
        if execution_data.docker_port:
            from ...config.auth_config import settings
            docker_host = settings.DOCKER_HOST_IP
            execution_data.docker_access_url = f"http://{docker_host}:{execution_data.docker_port}"
        execution_list.append(execution_data)
    
    return ResponseModel(data={
        "items": execution_list,
        "total": total,
        "page": skip // limit + 1,
        "size": limit,
        "pages": (total + limit - 1) // limit
    })

@router.get("/{task_id}/status")
async def get_task_status(
    task_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """获取任务详细状态信息"""
    result = await db.execute(select(Task).where(Task.id == str(task_id)))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 非管理员只能查看自己的任务
    if not current_user.is_admin and task.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权查看此任务状态"
        )
    
    # 检查是否有正在执行的记录
    running_result = await db.execute(
        select(TaskExecution).where(
            TaskExecution.task_id == str(task_id),
            TaskExecution.status == ExecutionStatus.RUNNING
        )
    )
    running_execution = running_result.scalar_one_or_none()
    
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
    
    return ResponseModel(message="获取任务状态成功", data=status_info)

@router.post("/{task_id}/activate")
async def activate_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """激活任务"""
    result = await db.execute(select(Task).where(Task.id == str(task_id)))
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
            detail="任务已处于激活状态，无需重复激活"
        )
    elif task.status == TaskStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务正在执行中，无法激活。请先停止当前执行"
        )
    
    # 更新任务状态为激活
    await update_task_status(db, str(task_id), TaskStatus.ACTIVE)
    
    return ResponseModel(message="任务激活成功")

@router.post("/{task_id}/deactivate")
async def deactivate_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """停用任务"""
    result = await db.execute(select(Task).where(Task.id == str(task_id)))
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
    if task.status == TaskStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已处于暂停状态，无需重复停用"
        )
    elif task.status == TaskStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务正在执行中，无法停用。请先停止当前执行"
        )
    elif task.status != TaskStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，无法停用非激活状态的任务"
        )
    
    # 更新任务状态为停用
    await update_task_status(db, str(task_id), TaskStatus.PAUSED)
    
    return ResponseModel(message="任务已停用")



