"""
监控和清理相关任务
"""
from typing import Any, Dict, Optional, List
from uuid import UUID
from loguru import logger
from sqlalchemy import text
import subprocess

from .celeryconfig import celery_app
from .utils.task_progress_util import BaseTaskWithProgress
from .db import make_sync_session
from .db_tasks import (
    get_running_task_executions,
    cleanup_old_executions,
    get_task_execution_by_id,
    update_task_execution_status,
)
from .docker_management_tasks import (
    cleanup_old_containers_impl,
    cleanup_old_configs_impl,
    check_docker_host_connection_impl,
)
from .file_tasks import cleanup_task_files, cleanup_all_task_files
from datetime import datetime, timedelta
from .celeryconfig import redis_client
from ..data_platform_api.models.task import ExecutionStatus
from ..config.auth_config import settings


def check_docker_container_status(container_id: str) -> Dict[str, Any]:
    """
    检查 Docker 容器的实际状态
    
    Returns:
        dict: {
            "exists": bool,  # 容器是否存在
            "running": bool,  # 容器是否正在运行
            "status": str,  # 容器状态（running/exited/etc）
            "exit_code": int or None  # 退出码
        }
    """
    try:
        # 使用 docker inspect 获取容器状态
        inspect_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "docker", "inspect", "--format", 
            "{{.State.Status}}|{{.State.ExitCode}}|{{.State.Running}}", 
            container_id
        ]
        
        result = subprocess.run(
            inspect_command, 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            # 容器存在，解析状态信息
            status_info = result.stdout.strip().split("|")
            return {
                "exists": True,
                "status": status_info[0],
                "exit_code": int(status_info[1]) if status_info[1] != "<no value>" else None,
                "running": status_info[2] == "true"
            }
        else:
            # 容器不存在
            return {
                "exists": False,
                "running": False,
                "status": "not_found",
                "exit_code": None
            }
            
    except subprocess.TimeoutExpired:
        logger.error(f"检查容器状态超时: {container_id}")
        return {
            "exists": False,
            "running": False,
            "status": "timeout",
            "exit_code": None
        }
    except Exception as e:
        logger.error(f"检查容器状态异常: {container_id}, {e}")
        return {
            "exists": False,
            "running": False,
            "status": "error",
            "exit_code": None
        }


def monitor_task_execution_impl(
    self,
    execution_id: str,
    namespace: str = "monitoring"
):
    """监控任务执行状态"""
    try:
        self.update_status(0, "PENDING", "开始监控任务执行", namespace=namespace)
        
        # 获取任务执行记录
        execution = get_task_execution_by_id(UUID(execution_id))
        if not execution:
            raise ValueError(f"任务执行记录不存在: {execution_id}")
            
        self.update_status(20, "PROGRESS", "任务执行记录已获取", namespace=namespace)
        
        # 检查任务状态
        if execution.status == ExecutionStatus.RUNNING:
            # 检查心跳超时
            if execution.last_heartbeat:
                timeout_threshold = datetime.now() - timedelta(minutes=30)
                if execution.last_heartbeat < timeout_threshold:
                    logger.warning(f"任务执行心跳超时: {execution_id}")
                    update_task_execution_status(
                        UUID(execution_id),
                        "timeout",
                        error_log="任务执行心跳超时"
                    )
                    self.update_status(100, "SUCCESS", "任务执行心跳超时", namespace=namespace)
                    return {"status": "timeout", "message": "任务执行心跳超时"}
            
            self.update_status(50, "PROGRESS", "任务执行正常", namespace=namespace)
            
        elif execution.status in ["success", "failed", "cancelled"]:
            self.update_status(100, "SUCCESS", f"任务执行已完成: {execution.status}", namespace=namespace)
            return {"status": execution.status, "message": f"任务执行已完成: {execution.status}"}
        
        self.update_status(100, "SUCCESS", "任务执行监控完成", namespace=namespace)
        return {
            "status": "monitoring",
            "execution_id": execution_id,
            "current_status": execution.status,
            "last_heartbeat": execution.last_heartbeat
        }
        
    except Exception as e:
        logger.error(f"监控任务执行失败: {e}")
        self.update_status(0, "FAILURE", f"监控任务执行失败: {str(e)}", namespace=namespace)
        raise


def cleanup_task_resources_impl(
    self,
    task_id: str = None,
    namespace: str = "cleanup"
):
    """清理任务资源"""
    try:
        if task_id:
            self.update_status(0, "PENDING", f"开始清理任务资源: {task_id}", namespace=namespace)
            # 清理特定任务相关文件
            cleanup_task_files(task_id)
            self.update_status(30, "PROGRESS", "任务文件已清理", namespace=namespace)
        else:
            self.update_status(0, "PENDING", "开始全局清理任务资源", namespace=namespace)
            # 清理所有过期任务文件
            cleanup_all_task_files()
            self.update_status(30, "PROGRESS", "所有任务文件已清理", namespace=namespace)
        
        # 清理Docker容器
        cleanup_old_containers.delay()
        self.update_status(60, "PROGRESS", "Docker容器清理任务已提交", namespace=namespace)
        
        # 清理配置文件
        cleanup_old_configs.delay()
        self.update_status(90, "PROGRESS", "配置文件清理任务已提交", namespace=namespace)
        
        self.update_status(100, "SUCCESS", "任务资源清理完成", namespace=namespace)
        return {
            "success": True,
            "message": "任务资源清理完成",
            "task_id": task_id or "global"
        }
        
    except Exception as e:
        logger.error(f"清理任务资源失败: {e}")
        self.update_status(0, "FAILURE", f"清理任务资源失败: {str(e)}", namespace=namespace)
        raise


def health_check_impl(
    self,
    namespace: str = "health_check"
):
    """系统健康检查"""
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
        
        # 检查Docker主机连接
        try:
            docker_result = check_docker_host_connection.delay()
            docker_status = "checking"
            self.update_status(60, "PROGRESS", "Docker主机连接检查中", namespace=namespace)
        except Exception as e:
            docker_status = f"unhealthy: {str(e)}"
            logger.error(f"Docker主机健康检查失败: {e}")
            self.update_status(60, "PROGRESS", "Docker主机连接异常", namespace=namespace)
        
        # 检查运行中的任务
        try:
            running_executions = get_running_task_executions()
            running_tasks_count = len(running_executions)
            self.update_status(80, "PROGRESS", f"运行中任务: {running_tasks_count}", namespace=namespace)
        except Exception as e:
            running_tasks_count = 0
            logger.error(f"获取运行中任务失败: {e}")
            self.update_status(80, "PROGRESS", "获取运行中任务失败", namespace=namespace)
        
        # 生成健康报告
        health_report = {
            "database": db_status,
            "redis": redis_status,
            "docker": docker_status,
            "running_tasks": running_tasks_count,
            "timestamp": None
        }
        
        health_report["timestamp"] = datetime.now().isoformat()
        
        self.update_status(100, "SUCCESS", "系统健康检查完成", namespace=namespace)
        
        return {
            "status": "success",
            "message": "系统健康检查完成",
            "running_tasks": running_tasks_count,
            "health_report": health_report
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        self.update_status(0, "FAILURE", f"健康检查失败: {str(e)}", namespace=namespace)
        raise


def cleanup_old_data_impl(
    self,
    days: int = 30,
    namespace: str = "cleanup"
):
    """清理旧数据"""
    try:
        self.update_status(0, "PENDING", "开始清理旧数据", namespace=namespace)
        
        # 清理旧的任务执行记录
        cleaned_executions = cleanup_old_executions(days)
        self.update_status(30, "PROGRESS", f"清理了 {cleaned_executions} 条旧执行记录", namespace=namespace)
        
        # 清理旧的Docker容器
        cleanup_old_containers.delay()
        self.update_status(60, "PROGRESS", "Docker容器清理任务已提交", namespace=namespace)
        
        # 清理旧的配置文件
        cleanup_old_configs.delay()
        self.update_status(90, "PROGRESS", "配置文件清理任务已提交", namespace=namespace)
        
        self.update_status(100, "SUCCESS", "旧数据清理完成", namespace=namespace)
        return {
            "success": True,
            "message": "旧数据清理完成",
            "cleaned_executions": cleaned_executions,
            "days": days
        }
        
    except Exception as e:
        logger.error(f"清理旧数据失败: {e}")
        self.update_status(0, "FAILURE", f"清理旧数据失败: {str(e)}", namespace=namespace)
        raise


# Docker管理相关的Celery任务
@celery_app.task(
    name="cleanup_old_containers",
    base=BaseTaskWithProgress,
    bind=True,
    queue="cleanup",
)
def cleanup_old_containers(
    self,
    namespace: str = "cleanup"
):
    """清理旧的容器"""
    return cleanup_old_containers_impl(self, namespace)


@celery_app.task(
    name="cleanup_old_configs",
    base=BaseTaskWithProgress,
    bind=True,
    queue="cleanup",
)
def cleanup_old_configs(
    self,
    namespace: str = "cleanup"
):
    """清理旧的配置文件"""
    return cleanup_old_configs_impl(self, namespace)


@celery_app.task(
    name="check_docker_host_connection",
    base=BaseTaskWithProgress,
    bind=True,
    queue="health_check",
)
def check_docker_host_connection(
    self,
    namespace: str = "health_check"
):
    """检查Docker主机连接"""
    return check_docker_host_connection_impl(self, namespace)


def monitor_all_task_executions_impl(
    self,
    namespace: str = "monitoring"
):
    """监控所有正在执行的任务"""
    try:
        self.update_status(0, "PENDING", "开始监控所有任务执行", namespace=namespace)
        
        # 获取所有正在执行的任务
        running_executions = get_running_task_executions()
        self.update_status(20, "PROGRESS", f"找到 {len(running_executions)} 个正在执行的任务", namespace=namespace)
        
        timeout_count = 0
        processed_count = 0
        
        for execution in running_executions:
            try:
                # 检查心跳超时
                if execution.last_heartbeat:
                    timeout_threshold = datetime.now() - timedelta(minutes=30)
                    if execution.last_heartbeat < timeout_threshold:
                        logger.warning(f"任务执行心跳超时: {execution.id}")
                        update_task_execution_status(
                            execution.id,
                            ExecutionStatus.FAILED,
                            end_time=datetime.now(),
                            error_log="任务执行心跳超时"
                        )
                        timeout_count += 1
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"处理任务执行记录失败 {execution.id}: {e}")
                continue
        
        self.update_status(100, "SUCCESS", f"监控完成，处理了 {processed_count} 个任务，{timeout_count} 个超时", namespace=namespace)
        return {
            "total_executions": len(running_executions),
            "processed_count": processed_count,
            "timeout_count": timeout_count,
            "message": "所有任务监控完成"
        }
        
    except Exception as e:
        logger.error(f"监控所有任务执行失败: {e}")
        self.update_status(100, "FAILURE", f"监控失败: {str(e)}", namespace=namespace)
        raise


def heartbeat_monitor_impl(
    self,
    namespace: str = "heartbeat_monitor"
):
    """心跳监控任务 - 检测任务超时和失联，并检查Docker容器实际状态"""
    try:
        self.update_status(0, "PENDING", "开始心跳监控", namespace=namespace)
        
        # 获取所有正在执行的任务
        running_executions = get_running_task_executions()
        self.update_status(20, "PROGRESS", f"找到 {len(running_executions)} 个正在执行的任务", namespace=namespace)
        
        timeout_count = 0
        disconnect_count = 0
        container_stopped_count = 0
        processed_count = 0
        
        # 心跳超时配置（秒）
        heartbeat_timeout = settings.HEARTBEAT_TIMEOUT  # 默认5分钟
        max_timeout_count = 3  # 最大超时次数
        
        for execution in running_executions:
            try:
                processed_count += 1
                
                # 【新增】首先检查 Docker 容器实际状态
                if execution.docker_container_id:
                    container_status = check_docker_container_status(execution.docker_container_id)
                    
                    # 如果容器不存在或已停止，立即标记为失败
                    if not container_status.get("exists", False):
                        logger.warning(f"容器不存在，任务标记为失败: {execution.id}, 容器ID: {execution.docker_container_id}")
                        update_task_execution_status(
                            execution.id,
                            ExecutionStatus.FAILED,
                            end_time=datetime.now(),
                            error_log="Docker容器不存在或已被删除"
                        )
                        container_stopped_count += 1
                        continue
                    
                    if not container_status.get("running", False):
                        exit_code = container_status.get("exit_code")
                        status_str = container_status.get("status", "unknown")
                        
                        # 容器已停止，根据退出码判断是否成功
                        if exit_code == 0:
                            # 正常退出，但没有调用completion接口，标记为成功
                            logger.info(f"容器正常退出但未通知，标记为成功: {execution.id}, 容器ID: {execution.docker_container_id}")
                            update_task_execution_status(
                                execution.id,
                                ExecutionStatus.SUCCESS,
                                end_time=datetime.now(),
                                error_log=f"容器正常退出(exit_code=0)但未调用completion接口"
                            )
                        else:
                            # 异常退出
                            logger.error(f"容器异常退出，任务标记为失败: {execution.id}, 容器ID: {execution.docker_container_id}, 退出码: {exit_code}, 状态: {status_str}")
                            update_task_execution_status(
                                execution.id,
                                ExecutionStatus.FAILED,
                                end_time=datetime.now(),
                                error_log=f"Docker容器异常退出 (exit_code={exit_code}, status={status_str})"
                            )
                        container_stopped_count += 1
                        continue
                
                # 检查是否有心跳记录
                if not execution.last_heartbeat:
                    # 没有心跳记录，检查是否超过启动时间 + 心跳超时
                    if execution.start_time:
                        timeout_threshold = execution.start_time + timedelta(seconds=heartbeat_timeout)
                        if datetime.now() > timeout_threshold:
                            logger.warning(f"任务从未发送心跳，可能已失联: {execution.id}")
                            update_task_execution_status(
                                execution.id,
                                ExecutionStatus.FAILED,
                                end_time=datetime.now(),
                                error_log="任务启动后从未发送心跳，可能已失联"
                            )
                            disconnect_count += 1
                    continue
                
                # 检查心跳超时
                timeout_threshold = datetime.now() - timedelta(seconds=heartbeat_timeout)
                if execution.last_heartbeat < timeout_threshold:
                    # 从Redis获取超时计数
                    timeout_key = f"heartbeat_timeout_count:{execution.id}"
                    try:
                        current_count = redis_client.get(timeout_key)
                        current_count = int(current_count) + 1 if current_count else 1
                        redis_client.set(timeout_key, current_count, ex=heartbeat_timeout * 2)
                        
                        logger.warning(f"任务心跳超时第 {current_count} 次: {execution.id}")
                        
                        if current_count >= max_timeout_count:
                            # 超时三次，标记为失联
                            logger.error(f"任务连续超时 {current_count} 次，标记为失联: {execution.id}")
                            update_task_execution_status(
                                execution.id,
                                ExecutionStatus.FAILED,
                                end_time=datetime.now(),
                                error_log=f"任务连续心跳超时 {current_count} 次，已失联"
                            )
                            disconnect_count += 1
                            # 清除超时计数
                            redis_client.delete(timeout_key)
                        else:
                            timeout_count += 1
                            
                    except Exception as redis_e:
                        logger.error(f"处理Redis超时计数失败: {redis_e}")
                        # Redis异常时直接标记为超时
                        update_task_execution_status(
                            execution.id,
                            ExecutionStatus.FAILED,
                            end_time=datetime.now(),
                            error_log="心跳超时且Redis异常"
                        )
                        disconnect_count += 1
                else:
                    # 心跳正常，清除超时计数
                    timeout_key = f"heartbeat_timeout_count:{execution.id}"
                    try:
                        redis_client.delete(timeout_key)
                    except:
                        pass
                
            except Exception as e:
                logger.error(f"处理任务心跳监控失败 {execution.id}: {e}")
                continue
        
        self.update_status(100, "SUCCESS", 
                          f"心跳监控完成，处理了 {processed_count} 个任务，{timeout_count} 个超时，{disconnect_count} 个失联，{container_stopped_count} 个容器已停止", 
                          namespace=namespace)
        
        return {
            "total_executions": len(running_executions),
            "processed_count": processed_count,
            "timeout_count": timeout_count,
            "disconnect_count": disconnect_count,
            "container_stopped_count": container_stopped_count,
            "message": "心跳监控完成"
        }
        
    except Exception as e:
        logger.error(f"心跳监控任务失败: {e}")
        self.update_status(100, "FAILURE", f"心跳监控失败: {str(e)}", namespace=namespace)
        raise
