"""
数据采集相关任务
"""
from typing import Any, Dict, Optional
from uuid import UUID
import time
from loguru import logger

from .utils.task_progress_util import BaseTaskWithProgress
from .db_tasks import (
    save_task_execution_to_db,
    update_task_execution_status,
    get_task_by_id,
    get_user_by_id,
    update_task_status,
)
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
        
        # 获取任务信息
        task = get_task_by_id(UUID(task_id))
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
            
        # 获取执行者信息
        executor = get_user_by_id(task.creator_id)
        if not executor:
            raise ValueError(f"执行者不存在: {task.creator_id}")
            
        # 创建任务执行记录
        execution_data = {
            "task_id": UUID(task_id),
            "executor_id": task.creator_id,
            "execution_name": f"执行任务: {task.task_name}",
            "status": "running",
            "start_time": None,
            "end_time": None,
            "result_data": None,
            "error_log": None,
        }
        
        if not save_task_execution_to_db(execution_data):
            raise Exception("保存任务执行记录失败")
            
        self.update_status(10, "PROGRESS", "任务执行记录已创建", namespace=namespace)
        
        # 创建任务工作空间
        workspace_path = create_task_workspace(task_id, execution_id)
        self.update_status(20, "PROGRESS", "任务工作空间已创建", namespace=namespace)
        
        # 处理任务配置
        if config_data:
            config_saved = process_task_config_file(config_data, UUID(execution_id))
            if not config_saved:
                raise Exception("配置文件处理失败")
            self.update_status(30, "PROGRESS", "任务配置文件已生成", namespace=namespace)
        
        # 根据任务类型执行不同的逻辑
        if task.task_type.value == "docker-crawl":
            result = _execute_crawler_task_with_docker(task, execution_id, config_data)
        elif task.task_type.value == "api":
            result = _execute_api_task_with_docker(task, execution_id, config_data)
        elif task.task_type.value == "database":
            result = _execute_database_task_with_docker(task, execution_id, config_data)
        else:
            raise ValueError(f"不支持的任务类型: {task.task_type}")
            
        self.update_status(80, "PROGRESS", "任务执行完成，正在保存结果", namespace=namespace)
        
        # 保存任务结果
        if result:
            result_file_path = save_task_result_data(workspace_path, result)
            self.update_status(90, "PROGRESS", "任务结果已保存", namespace=namespace)
            
            # 更新任务执行状态
            update_task_execution_status(
                UUID(execution_id),
                "success",
                result_data=result,
                error_log=None
            )
            
            # 更新任务状态
            update_task_status(UUID(task_id), "completed")
            
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
                error_log=str(e)
            )
            update_task_status(UUID(task_id), "failed")
        except Exception as update_error:
            logger.error(f"更新任务状态失败: {update_error}")
        
        raise


def _execute_crawler_task_with_docker(task, execution_id: str, config_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """使用Docker执行爬虫任务"""
    container_id = None
    try:
        logger.info(f"使用Docker执行爬虫任务: {task.task_name}")
        
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
        docker_image = config_data.get("docker_image", "crawler-service:latest")
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
        
        # 监控容器执行 - 通过容器日志和状态监控
        max_wait_time = 7200  # 最大等待2小时（爬虫任务可能很长）
        check_interval = 30   # 每30秒检查一次
        waited_time = 0
        last_heartbeat = time.time()
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
                
                # 如果连续3次没有日志，检查容器状态
                if consecutive_empty_logs >= 3:
                    try:
                        # 检查容器是否还在运行
                        from .docker_management_tasks import get_container_status_impl
                        container_status = get_container_status_impl(None, container_id, "docker_management")
                        
                        if not container_status.get("exists", False):
                            logger.warning(f"容器不存在: {container_id}")
                            raise Exception("容器意外停止")
                        elif not container_status.get("running", False):
                            logger.info(f"容器已停止: {container_id}, 状态: {container_status.get('status')}")
                            # 容器正常停止，可能是任务完成
                            break
                        else:
                            # 容器还在运行，但日志为空，重置计数继续等待
                            logger.debug(f"容器运行中但日志为空: {container_id}")
                            consecutive_empty_logs = 0
                            
                    except Exception as e:
                        logger.warning(f"检查容器状态失败: {e}")
                        # 检查失败时继续等待，避免误判
            
            # 检查心跳超时（5分钟没有新日志认为超时）
            if time.time() - last_heartbeat > 300:
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
        raise
    finally:
        # 清理配置文件
        try:
            cleanup_remote_config_files(UUID(execution_id))
        except:
            pass


def _execute_api_task_with_docker(task, execution_id: str, config_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """使用Docker执行API任务"""
    container_id = None
    try:
        logger.info(f"使用Docker执行API任务: {task.task_name}")
        
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
        docker_image = config_data.get("docker_image", "data-collection-api:latest")
        logger.info(f"使用Docker镜像: {docker_image}")
        config_path = f"/tmp/task_configs/{execution_id}/config.json"
        
        container_id = start_docker_task_container(
            UUID(execution_id),
            docker_image,
            config_path
        )
        
        logger.info(f"Docker API容器已启动: {container_id}")
        
        # 监控容器执行
        max_wait_time = 1800  # 最大等待30分钟
        check_interval = 5    # 每5秒检查一次
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


def _execute_database_task_with_docker(task, execution_id: str, config_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """使用Docker执行数据库任务"""
    container_id = None
    try:
        logger.info(f"使用Docker执行数据库任务: {task.task_name}")
        
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
        docker_image = config_data.get("docker_image", "data-collection-database:latest")
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
        max_wait_time = 2400  # 最大等待40分钟
        check_interval = 10   # 每10秒检查一次
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
