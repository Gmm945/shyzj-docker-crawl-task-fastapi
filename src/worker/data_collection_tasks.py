"""
数据采集相关任务
"""
from typing import Any, Dict, Optional
from uuid import UUID
import time
import os
import subprocess
from loguru import logger
from datetime import datetime

from .utils.task_progress_util import BaseTaskWithProgress
from .db_tasks import (
    save_task_execution_to_db,
    update_task_execution_status,
    get_task_by_id,
    get_user_by_id,
    update_task_status,
    make_sync_session,
    get_task_execution_by_id,
)
from ..config.auth_config import settings
from ..data_platform_api.models.task import Task, TaskExecution, ExecutionStatus
from ..user_manage.models.user import User
from .file_tasks import (
    cleanup_task_workspace,
    create_task_workspace,
    process_task_config_file,
    save_task_result_data,
    validate_task_config,
    start_docker_task_container,
    stop_docker_task_container,
    cleanup_remote_config_files,
    get_docker_container_logs,
)
from .monitoring_tasks import check_docker_container_status


def execute_data_collection_task_impl(
    self,
    task_id: str,
    execution_id: str,
    config_data: Optional[Dict[str, Any]] = None,
    namespace: str = "data_collection"
):
    """执行数据采集任务实现"""
    try:
        logger.info(f"Worker接收到的config_data: {config_data}")
        self.update_status(0, "PENDING", "开始执行数据采集任务", namespace=namespace)
        
        # 在同一个会话中获取任务和执行者信息
        with make_sync_session() as session:
            # 重新查询任务以确保在会话中
            task_in_session = session.query(Task).filter(Task.id == task_id).first()
            if not task_in_session:
                raise ValueError(f"任务不存在: {task_id}")
            
            # 获取执行者信息
            executor = session.query(User).filter(User.id == task_in_session.creator_id).first()
            if not executor:
                raise ValueError(f"执行者不存在: {task_in_session.creator_id}")
            
            # 提取任务信息（在会话内获取所有需要的数据）
            task_name = task_in_session.task_name
            task_type = task_in_session.task_type
            creator_id = task_in_session.creator_id
            
            # 标记已有执行记录为 running（由API创建）
            update_task_execution_status(UUID(execution_id), "running")
            
        self.update_status(10, "PROGRESS", "任务执行记录已创建", namespace=namespace)
        
        # 创建任务工作空间
        workspace_path = create_task_workspace(UUID(execution_id))
        self.update_status(20, "PROGRESS", "任务工作空间已创建", namespace=namespace)
        
        # 处理任务配置
        if config_data:
            config_saved = process_task_config_file(config_data, UUID(execution_id))
            if not config_saved:
                raise Exception("配置文件处理失败")
            self.update_status(30, "PROGRESS", "任务配置文件已生成", namespace=namespace)
        
        # 根据任务类型执行不同的逻辑
        if task_type == "docker-crawl":
            result = _execute_crawler_task_with_docker(task_name, execution_id, config_data)
        elif task_type == "api":
            result = _execute_api_task_with_docker(task_name, execution_id, config_data)
        elif task_type == "database":
            result = _execute_database_task_with_docker(task_name, execution_id, config_data)
        else:
            raise ValueError(f"不支持的任务类型: {task_type}")
        self.update_status(80, "PROGRESS", "Docker容器已启动，任务正在执行中", namespace=namespace)
        # 保存任务启动结果（不是最终结果）
        if result:
            save_task_result_data(UUID(execution_id), result)
            self.update_status(90, "PROGRESS", "任务启动信息已保存", namespace=namespace)
            # 注意：这里不更新任务执行状态为success，因为任务还在执行中
            # 最终的成功/失败状态将由容器的completion接口通知更新
        self.update_status(100, "SUCCESS", "Docker容器启动成功，等待任务执行完成", namespace=namespace)
        
        # 注意：不在这里清理工作空间！
        # 配置文件需要保留给容器使用，容器完成后会自动清理
        # 或由定时清理任务统一清理旧文件
        # cleanup_task_workspace(UUID(execution_id))
        
        return {
            "success": True,
            "task_id": task_id,
            "execution_id": execution_id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"数据采集任务执行启动失败: {e}")
        self.update_status(0, "FAILURE", f"数据采集任务执行启动失败: {str(e)}", namespace=namespace)
        
        # 更新任务执行状态为失败
        try:
            update_task_execution_status(
                UUID(execution_id),
                "failed",
                result_data=None,
                end_time=datetime.now(),
                error_log=str(e)
            )
            # 移除自动暂停任务逻辑：任务失败就是失败，不自动暂停
        except Exception as update_error:
            logger.error(f"更新任务状态失败: {update_error}")
        
        raise


def _execute_crawler_task_with_docker(task_name: str, execution_id: str, config_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """使用Docker执行爬虫任务"""
    container_name = None
    container_id = None
    try:
        logger.info(f"使用Docker执行爬虫任务: {task_name}")
        # 验证配置
        cfg = config_data or {}
        logger.info(f"收到配置数据: {cfg is not None}, keys: {list(cfg.keys()) if cfg else '空'}")
        if cfg:
            is_valid, error_msg = validate_task_config(cfg)
            if not is_valid:
                raise ValueError(f"配置验证失败: {error_msg}")
        
        # 处理配置文件 - 将配置保存到文件供容器使用
        config_saved = process_task_config_file(cfg, UUID(execution_id))
        if not config_saved:
            raise Exception("配置文件处理失败")
        
        # 从数据库获取配置文件路径
        execution = get_task_execution_by_id(execution_id)
        config_path = execution.docker_config_path if execution and execution.docker_config_path else f"/tmp/task_configs/{execution_id}/config.json"
        logger.info(f"使用配置文件路径: {config_path}")
        
        # 启动Docker容器 - 从配置文件获取镜像名称
        docker_image = (cfg.get("docker_image") or settings.DOCKER_CRAWLER_IMAGE)
        if not docker_image:
            raise Exception("未配置 Docker 镜像名称，请在 .env 设置 DOCKER_CRAWLER_IMAGE 或在任务配置中提供 docker_image")
        logger.info(f"使用Docker镜像: {docker_image}")
        
        # 爬虫直接输出到HDFS，不需要本地挂载卷
        additional_volumes = {}
        
        container_id = start_docker_task_container(
            UUID(execution_id),
            docker_image,
            config_path,
            additional_volumes
        )
        
        # 容器名格式：task-{execution_id}
        container_name = f"task-{execution_id}"
        logger.info(f"Docker爬虫容器已启动: {container_name} (ID: {container_id})")
        
        # 容器已启动，等待任务完成通知
        logger.info(f"容器已启动，等待任务完成通知: {container_id}")
        
        # 更新执行记录：写入容器名与开始时间、状态running
        try:
            update_task_execution_status(
                UUID(execution_id),
                "running",
                docker_container_name=container_name,
                docker_container_id=container_id,
                start_time=datetime.now()
            )
        except Exception as _:
            pass
        
        # 容器启动成功，立即返回 - 后续状态更新由容器主动通知
        logger.info(f"爬虫容器启动成功: {container_name} (ID: {container_id})")
        logger.info(f"容器将通过 /api/v1/monitoring/heartbeat 接口发送心跳")
        logger.info(f"容器将通过 /api/v1/monitoring/completion 接口通知任务完成")
        
        # 返回容器启动成功的结果
        result = {
            "task_type": "crawler",
            "status": "started",
            "container_name": container_name,
            "message": "爬虫容器已启动，任务正在执行中"
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Docker爬虫任务执行失败: {e}")
        if container_id:
            try:
                stop_docker_task_container(container_id)
            except:
                pass
        # 标记执行失败
        try:
            update_task_execution_status(
                UUID(execution_id),
                "failed",
                end_time=datetime.now(),
                error_log=str(e)
            )
        except Exception:
            pass
        raise
    finally:
        # 清理配置文件
        try:
            cleanup_remote_config_files(UUID(execution_id))
        except:
            pass


def _execute_api_task_with_docker(task_name: str, execution_id: str, config_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """使用Docker执行API任务"""
    container_id = None
    try:
        logger.info(f"使用Docker执行API任务: {task_name}")
        
        # 验证配置
        if config_data:
            is_valid, error_msg = validate_task_config(config_data)
            if not is_valid:
                raise ValueError(f"配置验证失败: {error_msg}")
        
        # 处理配置文件
        if config_data:
            config_saved = process_task_config_file(config_data, UUID(execution_id))
            if not config_saved:
                raise Exception("配置文件处理失败")
        
        # 从数据库获取配置文件路径
        execution = get_task_execution_by_id(execution_id)
        config_path = execution.docker_config_path if execution and execution.docker_config_path else f"/tmp/task_configs/{execution_id}/config.json"
        logger.info(f"使用配置文件路径: {config_path}")
        
        # 启动Docker容器 - 从配置文件获取镜像名称
        docker_image = config_data.get("docker_image", settings.DOCKER_API_IMAGE)
        logger.info(f"使用Docker镜像: {docker_image}")
        
        container_id = start_docker_task_container(
            UUID(execution_id),
            docker_image,
            config_path
        )
        
        # 容器名格式：task-{execution_id}
        container_name = f"task-{execution_id}"
        logger.info(f"Docker API容器已启动: {container_name} (ID: {container_id})")
        
        # 容器已启动，等待任务完成通知
        logger.info(f"容器已启动，等待任务完成通知: {container_id}")
        
        # 更新执行记录：写入容器名与开始时间、状态running
        try:
            update_task_execution_status(
                UUID(execution_id),
                "running",
                docker_container_name=container_name,
                docker_container_id=container_id,
                start_time=datetime.now()
            )
        except Exception as _:
            pass
        
        # 容器启动成功，立即返回 - 后续状态更新由容器主动通知
        logger.info(f"API容器启动成功: {container_name} (ID: {container_id})")
        
        # 返回启动成功状态，不等待执行完成
        result = {
            "task_type": "api",
            "status": "started",
            "container_name": container_name,
            "container_id": container_id,
            "message": "API容器已启动，任务正在执行中"
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Docker API任务执行失败: {e}")
        if container_id:
            try:
                stop_docker_task_container(container_id)
            except:
                pass
        # 标记执行失败
        try:
            update_task_execution_status(
                UUID(execution_id),
                "failed",
                end_time=datetime.now(),
                error_log=str(e)
            )
        except Exception:
            pass
        raise
    finally:
        # 清理配置文件
        try:
            cleanup_remote_config_files(UUID(execution_id))
        except:
            pass


def _execute_database_task_with_docker(task_name: str, execution_id: str, config_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """使用Docker执行数据库任务"""
    container_id = None
    try:
        logger.info(f"使用Docker执行数据库任务: {task_name}")
        
        # 验证配置
        if config_data:
            is_valid, error_msg = validate_task_config(config_data)
            if not is_valid:
                raise ValueError(f"配置验证失败: {error_msg}")
        
        # 处理配置文件
        if config_data:
            config_saved = process_task_config_file(config_data, UUID(execution_id))
            if not config_saved:
                raise Exception("配置文件处理失败")
        
        # 从数据库获取配置文件路径
        execution = get_task_execution_by_id(execution_id)
        config_path = execution.docker_config_path if execution and execution.docker_config_path else f"/tmp/task_configs/{execution_id}/config.json"
        logger.info(f"使用配置文件路径: {config_path}")
        
        # 启动Docker容器 - 从配置文件获取镜像名称
        docker_image = config_data.get("docker_image", settings.DOCKER_DATABASE_IMAGE)
        logger.info(f"使用Docker镜像: {docker_image}")
        
        # 数据库任务可能需要额外的卷挂载
        additional_volumes = {
            "/tmp/db_backups": "/app/backups"  # 数据库备份目录
        }
        
        container_id = start_docker_task_container(
            UUID(execution_id),
            docker_image,
            config_path,
            additional_volumes
        )
        
        # 容器名格式：task-{execution_id}
        container_name = f"task-{execution_id}"
        logger.info(f"Docker数据库容器已启动: {container_name} (ID: {container_id})")
        
        # 容器已启动，等待任务完成通知
        logger.info(f"容器已启动，等待任务完成通知: {container_id}")
        
        # 更新执行记录：写入容器名与开始时间、状态running
        try:
            update_task_execution_status(
                UUID(execution_id),
                "running",
                docker_container_name=container_name,
                docker_container_id=container_id,
                start_time=datetime.now()
            )
        except Exception as _:
            pass
        
        # 容器启动成功，立即返回 - 后续状态更新由容器主动通知
        logger.info(f"数据库容器启动成功: {container_name} (ID: {container_id})")
        
        # 返回启动成功状态，不等待执行完成
        result = {
            "task_type": "database",
            "status": "started",
            "container_name": container_name,
            "container_id": container_id,
            "message": "数据库容器已启动，任务正在执行中"
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Docker数据库任务执行失败: {e}")
        if container_id:
            try:
                stop_docker_task_container(container_id)
            except:
                pass
        # 标记执行失败
        try:
            update_task_execution_status(
                UUID(execution_id),
                "failed",
                end_time=datetime.now(),
                error_log=str(e)
            )
        except Exception:
            pass
        raise
    finally:
        # 清理配置文件
        try:
            cleanup_remote_config_files(UUID(execution_id))
        except:
            pass
