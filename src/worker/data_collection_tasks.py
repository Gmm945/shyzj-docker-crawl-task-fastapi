"""
数据采集相关任务
"""
from typing import Any, Dict, Optional
from uuid import UUID
import time
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
)
from ..config.auth_config import settings
from ..data_platform_api.models.task import Task, TaskExecution
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


def execute_data_collection_task_impl(
    self,
    task_id: str,
    execution_id: str,
    config_data: Optional[Dict[str, Any]] = None,
    namespace: str = "data_collection"
):
    """执行数据采集任务实现"""
    try:
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
            task_type = task_in_session.task_type.value
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
            
        self.update_status(80, "PROGRESS", "任务执行完成，正在保存结果", namespace=namespace)
        
        # 保存任务结果
        if result:
            save_task_result_data(UUID(execution_id), result)
            self.update_status(90, "PROGRESS", "任务结果已保存", namespace=namespace)
            
            # 更新任务执行状态
            update_task_execution_status(
                UUID(execution_id),
                "success",
                result_data=result,
                end_time=datetime.now(),
                error_log=None
            )
            
            # 更新任务状态
            update_task_status(task_id, "completed")
            
        self.update_status(100, "SUCCESS", "数据采集任务执行成功", namespace=namespace)
        
        # 清理工作空间
        cleanup_task_workspace(task_id, execution_id)
        
        return {
            "success": True,
            "task_id": task_id,
            "execution_id": execution_id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"数据采集任务执行失败: {e}")
        self.update_status(0, "FAILURE", f"数据采集任务执行失败: {str(e)}", namespace=namespace)
        
        # 更新任务执行状态为失败
        try:
            update_task_execution_status(
                UUID(execution_id),
                "failed",
                result_data=None,
                end_time=datetime.now(),
                error_log=str(e)
            )
            update_task_status(task_id, "stopped")
        except Exception as update_error:
            logger.error(f"更新任务状态失败: {update_error}")
        
        raise


def _execute_crawler_task_with_docker(task_name: str, execution_id: str, config_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """使用Docker执行爬虫任务"""
    container_id = None
    try:
        logger.info(f"使用Docker执行爬虫任务: {task_name}")
        
        # 验证配置
        cfg = config_data or {}
        if cfg:
            is_valid, error_msg = validate_task_config(cfg)
            if not is_valid:
                raise ValueError(f"配置验证失败: {error_msg}")
        
        # 处理配置文件
        if cfg:
            # 为测试与稳定心跳，若未提供目标与延迟，设置约1分钟的默认爬取参数
            try:
                if cfg.get("task_type") == "docker-crawl":
                    if not cfg.get("target_urls") and cfg.get("base_url"):
                        # 30 次 × 2 秒 ≈ 60 秒
                        cfg["target_urls"] = [cfg["base_url"]] * 30
                    if not cfg.get("delay"):
                        cfg["delay"] = 2
            except Exception:
                pass
            config_saved = process_task_config_file(cfg, UUID(execution_id))
            if not config_saved:
                raise Exception("配置文件处理失败")
        
        # 启动Docker容器 - 从配置文件获取镜像名称
        docker_image = (cfg.get("docker_image") or settings.DOCKER_CRAWLER_IMAGE)
        if not docker_image:
            raise Exception("未配置 Docker 镜像名称，请在 .env 设置 DOCKER_CRAWLER_IMAGE 或在任务配置中提供 docker_image")
        logger.info(f"使用Docker镜像: {docker_image}")
        config_path = f"/tmp/task_configs/{execution_id}/config.json"
        
        # 添加额外的卷挂载
        additional_volumes = {
            "/tmp/crawler_outputs": "/app/output"  # 爬虫输出目录挂载
        }
        
        container_id = start_docker_task_container(
            UUID(execution_id),
            docker_image,
            config_path,
            additional_volumes
        )
        
        logger.info(f"Docker爬虫容器已启动: {container_id}")
        # 更新执行记录：写入容器ID与开始时间、状态running
        try:
            update_task_execution_status(
                UUID(execution_id),
                "running",
                docker_container_id=container_id,
                start_time=datetime.now()
            )
        except Exception as _:
            pass
        
        # 监控容器执行 - 通过容器日志和状态监控
        # 监控参数：最大等待与轮询间隔可配置（支持超长任务）
        max_wait_time = getattr(settings, "TASK_TIMEOUT", 172800)  # 默认48小时
        check_interval = getattr(settings, "MONITOR_CHECK_INTERVAL", 30)
        waited_time = 0
        last_heartbeat = time.time()
        heartbeat_timeout = getattr(settings, "HEARTBEAT_TIMEOUT", 300)
        startup_grace = getattr(settings, "HEARTBEAT_REDUNDANCY", 60)
        consecutive_empty_logs = 0  # 连续空日志计数
        
        logger.info(f"开始监控爬虫容器: {container_id}, 最大等待时间: {max_wait_time}秒")
        
        while waited_time < max_wait_time:
            time.sleep(check_interval)
            waited_time += check_interval
            
            logger.debug(f"监控检查 - 已等待: {waited_time}秒, 容器: {container_id}")
            
            # 检查容器日志
            container_logs = get_docker_container_logs(container_id, 20)
            if container_logs:
                last_heartbeat = time.time()
                consecutive_empty_logs = 0
                
                # 检查是否有完成标志
                if "爬虫容器服务结束" in container_logs:
                    logger.info("检测到爬虫任务执行完成标志")
                    break
                elif "爬虫任务执行异常" in container_logs or "ERROR" in container_logs.upper():
                    logger.error("检测到爬虫任务执行异常")
                    raise Exception("爬虫任务执行失败")
                elif "心跳发送成功" in container_logs:
                    # 检测到心跳发送，说明任务还在正常进行
                    logger.debug("检测到心跳发送，任务正常进行中")
                else:
                    # 有其他日志输出，说明容器还在工作
                    logger.debug("容器有日志输出，继续监控")
            else:
                consecutive_empty_logs += 1
                logger.debug(f"容器日志为空，连续次数: {consecutive_empty_logs}")
                
                # 如果连续多次没有日志，检查容器状态
                if consecutive_empty_logs >= 3:
                    try:
                        # 本地快速检查容器状态
                        from .file_tasks import get_docker_container_status
                        cs = get_docker_container_status(container_id)
                        if cs and not cs.get("exists"):
                            logger.warning(f"容器不存在: {container_id}")
                            # 标记失败并退出
                            raise Exception("容器意外停止")
                        elif cs and not cs.get("running"):
                            logger.info(f"容器已停止: {container_id}, 状态: {cs.get('status')}")
                            break
                        else:
                            # 容器还在运行，但日志为空，重置计数继续等待
                            logger.debug(f"容器运行中但日志为空: {container_id}")
                            consecutive_empty_logs = 0
                            
                    except Exception as e:
                        logger.warning(f"检查容器状态失败: {e}")
                        # 检查失败时继续等待，避免误判
            
            # 检查心跳超时（使用可配置阈值并考虑启动宽限期）
            if waited_time > startup_grace and (time.time() - last_heartbeat > heartbeat_timeout):
                logger.warning("爬虫任务心跳超时，强制停止容器")
                stop_docker_task_container(container_id)
                raise Exception("爬虫任务心跳超时")
        
        if waited_time >= max_wait_time:
            logger.warning("爬虫任务执行超时，强制停止容器")
            stop_docker_task_container(container_id)
            raise Exception("爬虫任务执行超时")
        
        # 处理输出结果
        result = {
            "task_type": "crawler",
            "status": "success",
            "container_id": container_id,
            "message": "爬虫任务执行成功",
            "execution_time": f"{waited_time}秒"
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
        
        # 启动Docker容器 - 从配置文件获取镜像名称
        docker_image = config_data.get("docker_image", settings.DOCKER_API_IMAGE)
        logger.info(f"使用Docker镜像: {docker_image}")
        config_path = f"/tmp/task_configs/{execution_id}/config.json"
        
        container_id = start_docker_task_container(
            UUID(execution_id),
            docker_image,
            config_path
        )
        
        logger.info(f"Docker API容器已启动: {container_id}")
        
        # 监控容器执行
        max_wait_time = getattr(settings, "TASK_TIMEOUT", 172800)
        check_interval = getattr(settings, "MONITOR_CHECK_INTERVAL", 30)
        waited_time = 0
        
        while waited_time < max_wait_time:
            time.sleep(check_interval)
            waited_time += check_interval
            
            # 检查容器状态
            logs = get_docker_container_logs(container_id, 30)
            if logs and "API_TASK_COMPLETED" in logs:
                logger.info("API任务执行完成")
                break
            elif logs and "API_TASK_FAILED" in logs:
                raise Exception("API任务执行失败")
            elif not logs:
                # 本地快速判断容器状态
                from .file_tasks import get_docker_container_status
                cs = get_docker_container_status(container_id)
                if cs and not cs.get("exists"):
                    raise Exception("容器意外停止")
                if cs and not cs.get("running"):
                    logger.info(f"容器已停止: {container_id}, 状态: {cs.get('status')}")
                    break
        
        if waited_time >= max_wait_time:
            logger.warning("API任务执行超时，强制停止容器")
            stop_docker_task_container(container_id)
            raise Exception("API任务执行超时")
        
        # 处理输出结果
        result = {
            "task_type": "api",
            "status": "success",
            "container_id": container_id,
            "message": "API任务执行成功",
            "logs": logs
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Docker API任务执行失败: {e}")
        if container_id:
            try:
                stop_docker_task_container(container_id)
            except:
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
        
        # 启动Docker容器 - 从配置文件获取镜像名称
        docker_image = config_data.get("docker_image", settings.DOCKER_DATABASE_IMAGE)
        logger.info(f"使用Docker镜像: {docker_image}")
        config_path = f"/tmp/task_configs/{execution_id}/config.json"
        
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
        
        logger.info(f"Docker数据库容器已启动: {container_id}")
        
        # 监控容器执行
        max_wait_time = getattr(settings, "TASK_TIMEOUT", 172800)
        check_interval = getattr(settings, "MONITOR_CHECK_INTERVAL", 30)
        waited_time = 0
        
        while waited_time < max_wait_time:
            time.sleep(check_interval)
            waited_time += check_interval
            
            # 检查容器状态
            logs = get_docker_container_logs(container_id, 50)
            if logs and "DB_TASK_COMPLETED" in logs:
                logger.info("数据库任务执行完成")
                break
            elif logs and "DB_TASK_FAILED" in logs:
                raise Exception("数据库任务执行失败")
            elif not logs:
                from .file_tasks import get_docker_container_status
                cs = get_docker_container_status(container_id)
                if cs and not cs.get("exists"):
                    raise Exception("容器意外停止")
                if cs and not cs.get("running"):
                    logger.info(f"容器已停止: {container_id}, 状态: {cs.get('status')}")
                    break
        
        if waited_time >= max_wait_time:
            logger.warning("数据库任务执行超时，强制停止容器")
            stop_docker_task_container(container_id)
            raise Exception("数据库任务执行超时")
        
        # 处理输出结果
        result = {
            "task_type": "database",
            "status": "success",
            "container_id": container_id,
            "message": "数据库任务执行成功",
            "logs": logs
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Docker数据库任务执行失败: {e}")
        if container_id:
            try:
                stop_docker_task_container(container_id)
            except:
                pass
        raise
    finally:
        # 清理配置文件
        try:
            cleanup_remote_config_files(UUID(execution_id))
        except:
            pass
