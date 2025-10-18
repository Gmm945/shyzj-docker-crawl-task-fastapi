from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from typing import List, Optional
from uuid import UUID
from loguru import logger
from datetime import datetime

from ...config.auth_config import settings
from ...db_util.core import DBSessionDep
from ...user_manage.models.user import User
from ...common.schemas.base import ResponseModel
from ...user_manage.service.security import check_permissions
from ...worker.main import execute_data_collection_task, stop_docker_container
from ..models.task import Task, TaskStatus, ExecutionStatus, TriggerMethod
from ..schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskExecutionResponse, 
    TaskPagination, TriggerMethod
)
from ..service.task import (
    create_task,
    get_task_by_id,
    get_task_by_name,
    get_page_tasks,
    get_page_total,
    get_task_by_id_with_permission,
    get_running_execution_by_task_id,
    update_task_with_validation,
    delete_task_with_validation,
    create_task_execution,
    stop_task_execution,
    get_task_executions_paginated,
    get_task_status_info,
    activate_task_with_validation,
    deactivate_task_with_validation,
    fix_stopped_tasks_status,
    get_task_execution_summary
)
from ..service.scheduler import create_schedule
from ...utils.schedule_utils import ScheduleUtils

router = APIRouter()
obj = 'Task'  # 资源对象名称


@router.post("/add")
async def add_task(
    req_body: TaskCreate,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
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

    # 验证trigger_method和调度配置的一致性
    if req_body.trigger_method == TriggerMethod.AUTO:
        if not req_body.schedule_type or not req_body.schedule_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="自动任务必须提供schedule_type和schedule_config参数"
            )
        logger.info(f"创建自动任务，调度类型: {req_body.schedule_type}")
    else:
        if req_body.schedule_type or req_body.schedule_config:
            logger.warning(f"手动任务不需要调度配置，将忽略schedule_type和schedule_config")
        logger.info(f"创建手动任务")

    # 创建任务（直接激活）
    db_task = Task(
        task_name=req_body.task_name,
        task_type=req_body.task_type,
        trigger_method=req_body.trigger_method,
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
    
    # 如果是自动任务，则创建调度
    schedule_id = None
    if req_body.trigger_method == TriggerMethod.AUTO:
        # 计算下次执行时间
        next_run_time = ScheduleUtils.calculate_next_run_time(req_body.schedule_type, req_body.schedule_config)
        logger.info(f"为任务 {new_task.id} 创建调度，下次执行时间: {next_run_time}")
        
        # 创建调度
        schedule = await create_schedule(
            db, 
            str(new_task.id), 
            req_body.schedule_type, 
            req_body.schedule_config, 
            next_run_time
        )
        schedule_id = schedule.id
        logger.info(f"任务 {new_task.id} 的调度创建成功: {schedule_id}")
    
    response_data = {"task_id": new_task.id}
    if schedule_id:
        response_data["schedule_id"] = schedule_id
    
    res = ResponseModel(message="任务创建成功", data=response_data)
    return Response(content=res.model_dump_json())


@router.get("/list")
async def get_task_list(
    db: DBSessionDep,
    sort_bys: Optional[List[str]] = Query(["create_time"]),
    sort_orders: Optional[List[str]] = Query(["desc"]),
    pagination: TaskPagination = Depends(),
    user: User = Depends(check_permissions(obj))
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
    try:
        # 调用service层函数，传入用户权限信息
        tasks = await get_page_tasks(db, sort_bys, sort_orders, pagination, str(user.id), user.is_admin)
        total = await get_page_total(db, pagination, str(user.id), user.is_admin)
    except Exception as e:
        if "'STOPPED' is not among the defined enum values" in str(e):
            logger.warning("检测到数据库中存在STOPPED状态的任务，尝试修复...")
            # 使用service层函数修复
            success, message = await fix_stopped_tasks_status(db)
            if success:
                logger.info(message)
                # 重新查询
                tasks = await get_page_tasks(db, sort_bys, sort_orders, pagination, str(user.id), user.is_admin)
                total = await get_page_total(db, pagination, str(user.id), user.is_admin)
            else:
                logger.error(message)
                raise e
        else:
            raise e
    
    # 为每个任务添加执行统计信息
    task_list = []
    for task in tasks:
        task_data = TaskResponse.model_validate(task)
        # 获取执行统计信息
        execution_summary = await get_task_execution_summary(db, str(task.id))
        task_data.execution_summary = execution_summary
        task_list.append(task_data)
    
    return ResponseModel(message="获取任务列表成功", data={
        "items": task_list,
        "total": total,
        "page": pagination.page,
        "size": pagination.page_size,
        "pages": (total + pagination.page_size - 1) // pagination.page_size
    })

@router.get("/{task_id}")
async def get_task(
    task_id: UUID,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """
    获取任务详情

    **参数:**
    - `task_id`: 任务ID

    **返回:**
    - 包含任务详情的JSON响应
    """
    # 调用service层函数，传入用户权限信息
    task = await get_task_by_id(db, task_id, str(user.id), user.is_admin)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权限访问"
        )
    
    # 获取任务数据并添加访问地址信息
    task_data = TaskResponse.model_validate(task)
    
    # 获取执行统计信息
    execution_summary = await get_task_execution_summary(db, str(task_id))
    task_data.execution_summary = execution_summary
    
    # 如果有正在运行的执行，添加访问地址
    if hasattr(task_data, 'running_execution') and task_data.running_execution:
        execution = task_data.running_execution
        if execution.docker_port:
            docker_host = settings.DOCKER_HOST_IP
            execution.docker_access_url = f"http://{docker_host}:{execution.docker_port}"
    return ResponseModel(message="获取任务详情成功", data=task_data)


@router.put("/{task_id}")
async def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    db: DBSessionDep,
    current_user: User = Depends(check_permissions(obj))
):
    """更新任务"""
    # 使用service层函数进行更新
    task, message = await update_task_with_validation(
        db, task_id, task_data, str(current_user.id), current_user.is_admin
    )
    
    if not task:
        if "无权限访问" in message:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message
            )
        elif "正在执行中" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message
            )
    
    return ResponseModel(message=message)

@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    db: DBSessionDep,
    current_user: User = Depends(check_permissions(obj))
):
    """删除任务"""
    # 使用service层函数进行删除
    task, message = await delete_task_with_validation(
        db, task_id, str(current_user.id), current_user.is_admin
    )
    
    if not task:
        if "无权限访问" in message:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message
            )
        elif "正在执行中" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message
            )
    return ResponseModel(message=message)


@router.post("/{task_id}/execute")
async def execute_task_now(
    task_id: UUID,
    db: DBSessionDep,
    current_user: User = Depends(check_permissions(obj, "EXECUTE"))
):
    """立即执行任务"""
    # 使用service层函数获取任务
    task = await get_task_by_id_with_permission(db, task_id, str(current_user.id), current_user.is_admin)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权限访问"
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
    running_execution = await get_running_execution_by_task_id(db, str(task_id))
    if running_execution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已在执行中"
        )
    
    # 创建执行记录（避免包含非常规字符，使用固定前缀+时间戳+任务ID片段）
    timestamp = int(datetime.now().timestamp())
    execution_name = f"exec_{timestamp}_{str(task.id)[:8]}"
    
    # 使用service层函数创建执行记录
    db_execution = await create_task_execution(db, task_id, current_user.id, execution_name)
    
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
    db: DBSessionDep,
    current_user: User = Depends(check_permissions(obj, "STOP"))
):
    """停止正在执行的任务"""
    # 使用service层函数停止任务
    running_execution, message = await stop_task_execution(
        db, task_id, str(current_user.id), current_user.is_admin
    )
    
    if not running_execution:
        if "无权限访问" in message:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message
            )
        elif "没有正在执行" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message
            )
    
    # 停止Docker容器（通过Celery任务）
    if running_execution.docker_container_name:
        stop_docker_container.delay(running_execution.docker_container_name)
    return ResponseModel(message=message)


@router.get("/{task_id}/executions")
async def get_task_executions(
    db: DBSessionDep,
    task_id: UUID,
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    status: Optional[ExecutionStatus] = Query(None, description="执行状态筛选"),
    current_user: User = Depends(check_permissions(obj))
):
    """获取任务执行记录"""
    # 检查任务权限
    task = await get_task_by_id_with_permission(db, task_id, str(current_user.id), current_user.is_admin)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权限访问"
        )
    
    # 使用service层函数获取执行记录
    executions, total = await get_task_executions_paginated(
        db, task_id, page, page_size, status, str(current_user.id), current_user.is_admin
    )
    
    # 为每个执行记录添加访问地址
    execution_list = []
    for execution in executions:
        execution_data = TaskExecutionResponse.model_validate(execution)
        if execution_data.docker_port:
            docker_host = settings.DOCKER_HOST_IP
            execution_data.docker_access_url = f"http://{docker_host}:{execution_data.docker_port}"
        execution_list.append(execution_data)
    
    return ResponseModel(message="获取执行记录成功", data={
        "items": execution_list,
        "total": total,
        "page": page,
        "size": page_size,
        "pages": (total + page_size - 1) // page_size
    })

@router.get("/{task_id}/status")
async def get_task_status(
    task_id: UUID,
    db: DBSessionDep,
    current_user: User = Depends(check_permissions(obj))
):
    """获取任务详细状态信息"""
    # 使用service层函数获取任务状态信息
    status_info, message = await get_task_status_info(
        db, task_id, str(current_user.id), current_user.is_admin
    )
    
    if not status_info:
        if "无权限访问" in message:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message
            )
    
    return ResponseModel(message=message, data=status_info)

@router.post("/{task_id}/activate")
async def activate_task(
    task_id: UUID,
    db: DBSessionDep,
    current_user: User = Depends(check_permissions(obj))
):
    """激活任务"""
    # 使用service层函数激活任务
    task, message = await activate_task_with_validation(
        db, task_id, str(current_user.id), current_user.is_admin
    )
    
    if not task:
        if "无权限访问" in message:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message
            )
        elif "已处于激活状态" in message or "正在执行中" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message
            )
    
    return ResponseModel(message=message)

@router.post("/{task_id}/deactivate")
async def deactivate_task(
    task_id: UUID,
    db: DBSessionDep,
    current_user: User = Depends(check_permissions(obj))
):
    """停用任务"""
    # 使用service层函数停用任务
    task, message = await deactivate_task_with_validation(
        db, task_id, str(current_user.id), current_user.is_admin
    )
    
    if not task:
        if "无权限访问" in message:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message
            )
        elif "已处于暂停状态" in message or "正在执行中" in message or "无法停用非激活状态" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message
            )
    
    return ResponseModel(message=message)



