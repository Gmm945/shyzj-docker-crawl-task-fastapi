from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from sqlalchemy import desc, select
from uuid import UUID
from datetime import datetime, timedelta
from loguru import logger
from ...db_util.core import DBSessionDep, CacheManager
from ...db_util.db import sessionmanager
from ..models.task import TaskExecution, ExecutionStatus
from ..schemas.common import HeartbeatRequest, CompletionRequest, Response
from ...config.auth_config import settings
from ...worker.main import check_heartbeat_timeout

router = APIRouter()

# Redis键前缀
HEARTBEAT_PREFIX = "heartbeat:"
EXECUTION_STATUS_PREFIX = "execution_status:"

@router.post("/heartbeat")
async def heartbeat(
    heartbeat_data: HeartbeatRequest,
    background_tasks: BackgroundTasks,
    cache: CacheManager
):
    """
    容器心跳接口 - 高并发设计
    使用Redis缓存心跳数据，避免频繁写入数据库
    
    从远程Docker容器调用，用于报告任务执行状态和进度
    """
    try:
        execution_id = heartbeat_data.execution_id
        container_name = heartbeat_data.container_name
        current_time = datetime.now()
        
        # 验证execution_id格式（应该是UUID字符串）
        if not execution_id:
            logger.warning(f"Missing execution_id")
            return {"status": "error", "message": "Missing execution_id"}
        
        # 简单验证UUID格式（更灵活的验证）
        try:
            UUID(execution_id)
        except ValueError:
            logger.warning(f"Invalid execution_id format: {execution_id}")
            return {"status": "error", "message": "Invalid execution_id format"}
        
        # 心跳数据
        heartbeat_info = {
            "container_name": container_name,
            "status": heartbeat_data.status or "running",
            "progress": heartbeat_data.progress or {},
            "last_heartbeat": current_time.isoformat(),
            "timestamp": int(current_time.timestamp()),
            "client_timestamp": heartbeat_data.timestamp,  # 客户端时间戳
            "network_delay": None
        }
        
        # 计算网络延迟（如果有客户端时间戳）
        if heartbeat_data.timestamp:
            network_delay = int(current_time.timestamp()) - heartbeat_data.timestamp
            heartbeat_info["network_delay"] = network_delay
        
        # 存储到Redis（TTL设置为心跳超时时间的2倍）
        heartbeat_key_parts = [execution_id]
        cache.set_cache_sync(HEARTBEAT_PREFIX.rstrip(":"), heartbeat_key_parts, heartbeat_info, ttl=settings.HEARTBEAT_TIMEOUT * 2)
        
        # 异步更新数据库中的心跳时间（避免阻塞）
        try:
            background_tasks.add_task(update_heartbeat_in_db, execution_id, current_time)
            logger.debug(f"已提交异步任务更新心跳时间: {execution_id}")
        except Exception as bg_error:
            logger.error(f"提交异步任务失败: {bg_error}")
            # 异步任务失败不影响心跳响应
        
        logger.info(f"心跳接收成功 - 容器: {container_name}, 执行ID: {execution_id}, 时间: {current_time}")
        logger.debug(f"心跳数据: status={heartbeat_data.status}, progress={heartbeat_data.progress}")
        
        return {
            "status": "ok", 
            "timestamp": int(current_time.timestamp()),
            "execution_id": execution_id
        }
        
    except Exception as e:
        logger.error(f"心跳接口异常: {e}")
        # 即使Redis出错，也要返回成功，避免影响容器运行
        return {"status": "ok", "timestamp": int(datetime.now().timestamp())}

@router.post("/completion")
async def task_completion(
    completion_data: CompletionRequest,
    db: DBSessionDep,
    cache: CacheManager
):
    """任务完成通知接口"""
    try:
        execution_id = completion_data.execution_id
        container_name = completion_data.container_name
        success = completion_data.success
        result_data = completion_data.result_data or {}
        error_message = completion_data.error_message
        
        # 获取执行记录
        result = await db.execute(select(TaskExecution).where(TaskExecution.id == execution_id))
        execution = result.scalar_one_or_none()
        
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="执行记录不存在"
            )
        
        # 验证容器名（简化验证逻辑）
        if execution.docker_container_name and execution.docker_container_name != container_name:
            logger.warning(
                f"容器名不匹配: db={execution.docker_container_name}, got={container_name}"
            )
        # 如果数据库中没有容器名，则使用回调中的容器名
        elif not execution.docker_container_name and container_name:
            execution.docker_container_name = container_name
        
        # 更新执行状态
        execution.status = ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED
        execution.end_time = datetime.now()
        execution.result_data = result_data
        if error_message:
            execution.error_log = error_message
        
        await db.commit()
        
        # 清理Redis中的心跳数据
        heartbeat_key_parts = [str(execution_id)]
        cache.delete_cache(HEARTBEAT_PREFIX.rstrip(":"), heartbeat_key_parts)
        
        logger.info(f"任务完成通知: execution_id={execution_id}, success={success}")
        
        return Response(message="任务完成通知已处理")
        
    except Exception as e:
        logger.error(f"任务完成通知异常: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理任务完成通知失败: {str(e)}"
        )

@router.get("/execution/{execution_id}/status")
async def get_execution_status(
    execution_id: str,
    db: DBSessionDep,
    cache: CacheManager
):
    """获取执行状态（优先从Redis获取实时数据）"""
    try:
        # 先从Redis获取实时心跳数据
        heartbeat_key_parts = [str(execution_id)]
        heartbeat_data = await cache.get_cache(HEARTBEAT_PREFIX.rstrip(":"), heartbeat_key_parts)
        
        # 从数据库获取执行记录
        result = await db.execute(select(TaskExecution).where(TaskExecution.id == execution_id))
        execution = result.scalar_one_or_none()
        
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="执行记录不存在"
            )
        
        response_data = {
            "execution_id": execution_id,
            "status": execution.status,
            "start_time": execution.start_time.isoformat() if execution.start_time else None,
            "end_time": execution.end_time.isoformat() if execution.end_time else None,
            "container_name": execution.docker_container_name,
            "result_data": execution.result_data,
            "error_log": execution.error_log,
        }
        
        # 如果有Redis心跳数据，添加实时信息
        if heartbeat_data:
            response_data.update({
                "last_heartbeat": heartbeat_data.get("last_heartbeat"),
                "progress": heartbeat_data.get("progress"),
                "real_time_status": heartbeat_data.get("status"),
            })
        
        return Response(data=response_data)
        
    except Exception as e:
        logger.error(f"获取执行状态异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取执行状态失败: {str(e)}"
        )

@router.get("/executions/active")
async def get_active_executions(
    db: DBSessionDep,
    cache: CacheManager,
    limit: int = 100
):
    """获取活跃的执行任务（包含实时心跳信息）"""
    try:
        # 从数据库获取运行中的任务
        result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.status == ExecutionStatus.RUNNING)
            .order_by(desc(TaskExecution.start_time))
            .limit(limit)
        )
        active_executions = result.scalars().all()
        
        result_list = []
        for execution in active_executions:
            execution_data = {
                "execution_id": execution.id,
                "task_id": execution.task_id,
                "execution_name": execution.execution_name,
                "status": execution.status,
                "start_time": execution.start_time.isoformat() if execution.start_time else None,
                "container_name": execution.docker_container_name,
            }
            
            # 获取Redis中的心跳数据
            heartbeat_key_parts = [str(execution.id)]
            heartbeat_data = await cache.get_cache(HEARTBEAT_PREFIX.rstrip(":"), heartbeat_key_parts)
            
            if heartbeat_data:
                execution_data.update({
                    "last_heartbeat": heartbeat_data.get("last_heartbeat"),
                    "progress": heartbeat_data.get("progress"),
                    "real_time_status": heartbeat_data.get("status"),
                    "is_alive": True
                })
            else:
                execution_data["is_alive"] = False
            
            result_list.append(execution_data)
        
        return Response(data=result_list)
        
    except Exception as e:
        logger.error(f"获取活跃执行任务异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取活跃执行任务失败: {str(e)}"
        )

@router.get("/statistics")
async def get_monitoring_statistics(
    db: DBSessionDep,
    days: int = 7
):
    """获取监控统计数据"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 统计指定时间范围内的执行记录
        result = await db.execute(
            select(TaskExecution).where(
                TaskExecution.create_time >= start_date,
                TaskExecution.create_time <= end_date
            )
        )
        executions = result.scalars().all()
        
        total_executions = len(executions)
        successful_executions = len([e for e in executions if e.status == ExecutionStatus.SUCCESS])
        failed_executions = len([e for e in executions if e.status == ExecutionStatus.FAILED])
        running_executions = len([e for e in executions if e.status == ExecutionStatus.RUNNING])
        
        # 运行中的任务
        running_result = await db.execute(
            select(TaskExecution).where(TaskExecution.status == ExecutionStatus.RUNNING)
        )
        current_running = len(running_result.scalars().all())
        
        statistics = {
            "period_days": days,
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "running_executions": running_executions,
            "current_running": current_running,
            "success_rate": round(successful_executions / total_executions * 100, 2) if total_executions > 0 else 0,
            "failure_rate": round(failed_executions / total_executions * 100, 2) if total_executions > 0 else 0,
        }
        
        return Response(data=statistics)
        
    except Exception as e:
        logger.error(f"获取监控统计异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取监控统计失败: {str(e)}"
        )

async def update_heartbeat_in_db(execution_id: str, heartbeat_time: datetime):
    """异步更新数据库中的心跳时间"""
    try:
        logger.debug(f"开始更新心跳时间: {execution_id}, 时间: {heartbeat_time}")
        
        async with sessionmanager.session() as db:
            result = await db.execute(select(TaskExecution).where(TaskExecution.id == execution_id))
            execution = result.scalar_one_or_none()
            
            if execution:
                logger.debug(f"找到执行记录 {execution_id}, 当前状态: {execution.status}")
                
                # 更新心跳时间，不限制状态（心跳可能在任何状态下发送）
                old_heartbeat = execution.last_heartbeat
                execution.last_heartbeat = heartbeat_time
                await db.commit()
                
                logger.info(f"成功更新心跳时间 {execution_id}: {old_heartbeat} -> {heartbeat_time}")
            else:
                logger.warning(f"未找到执行记录: {execution_id}")
        
    except Exception as e:
        logger.error(f"更新数据库心跳时间异常 {execution_id}: {e}", exc_info=True)

@router.post("/check-timeouts")
async def check_heartbeat_timeouts():
    """检查心跳超时（定时任务调用）"""
    try:
        # 提交到Celery执行
        check_heartbeat_timeout.delay()
        
        return Response(message="心跳超时检查已启动")
        
    except Exception as e:
        logger.error(f"检查心跳超时异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查心跳超时失败: {str(e)}"
        )
