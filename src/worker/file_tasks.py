import os
import json
import shutil
import subprocess
from typing import Dict, Any, Optional
from uuid import UUID
from loguru import logger
from datetime import datetime

from .db import make_sync_session
from .db_tasks import update_task_execution_status, get_task_execution_by_id
from ..data_platform_api.models.task import TaskExecution
from ..config.auth_config import settings


def process_task_config_file(config_data: Dict[str, Any], execution_id: UUID) -> bool:
    """处理任务配置文件"""
    try:
        # 创建本地配置目录
        local_config_dir = f"/tmp/task_configs/{execution_id}"
        os.makedirs(local_config_dir, exist_ok=True)
        
        # 保存配置文件到本地
        local_config_file = os.path.join(local_config_dir, "config.json")
        with open(local_config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        # 上传配置文件到远程执行机器
        remote_config_path = upload_config_to_remote_machine(local_config_file, execution_id)
        
        # 更新执行记录
        update_task_execution_status(
            execution_id=execution_id,
            status="running",
            docker_config_path=remote_config_path
        )
        
        logger.info(f"Task config file processed and uploaded for execution {execution_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to process task config file: {str(e)}")
        update_task_execution_status(
            execution_id=execution_id,
            status="failed",
            error_log=str(e)
        )
        return False


def cleanup_task_files(execution_id: UUID) -> bool:
    """清理任务相关文件"""
    try:
        config_dir = f"/tmp/task_configs/{execution_id}"
        if os.path.exists(config_dir):
            shutil.rmtree(config_dir)
            logger.info(f"Cleaned up task files for execution {execution_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup task files: {str(e)}")
        return False


def cleanup_all_task_files() -> bool:
    """清理所有任务相关文件"""
    try:
        base_dir = "/tmp/task_configs"
        if os.path.exists(base_dir):
            # 清理超过7天的目录
            import time
            current_time = time.time()
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path):
                    # 检查目录的修改时间
                    if current_time - os.path.getmtime(item_path) > 7 * 24 * 3600:  # 7天
                        shutil.rmtree(item_path)
                        logger.info(f"Cleaned up old task files: {item}")
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup all task files: {str(e)}")
        return False


def save_task_result_data(execution_id: UUID, result_data: Dict[str, Any]) -> bool:
    """保存任务结果数据"""
    try:
        with make_sync_session() as session:
            execution = session.query(TaskExecution).filter(
                TaskExecution.id == execution_id
            ).first()
            if execution:
                execution.result_data = result_data
                execution.end_time = datetime.now()
                session.commit()
                logger.info(f"Task result data saved for execution {execution_id}")
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to save task result data: {str(e)}")
        return False


def process_docker_output(output_file: str, execution_id: UUID) -> Optional[Dict[str, Any]]:
    """处理 Docker 输出文件"""
    try:
        if not os.path.exists(output_file):
            logger.warning(f"Output file not found: {output_file}")
            return None
            
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 尝试解析为 JSON
        try:
            result_data = json.loads(content)
        except json.JSONDecodeError:
            # 如果不是 JSON，作为文本处理
            result_data = {
                "output_type": "text",
                "content": content,
                "file_size": len(content)
            }
        
        # 保存结果数据
        save_task_result_data(execution_id, result_data)
        
        logger.info(f"Docker output processed for execution {execution_id}")
        return result_data
        
    except Exception as e:
        logger.error(f"Failed to process docker output: {str(e)}")
        update_task_execution_status(
            execution_id=execution_id,
            status="failed",
            error_log=str(e)
        )
        return None


def create_task_workspace(execution_id: UUID) -> Optional[str]:
    """创建任务工作空间"""
    try:
        workspace_dir = f"/tmp/task_workspaces/{execution_id}"
        os.makedirs(workspace_dir, exist_ok=True)
        
        # 创建子目录
        subdirs = ["input", "output", "logs", "temp"]
        for subdir in subdirs:
            os.makedirs(os.path.join(workspace_dir, subdir), exist_ok=True)
        
        logger.info(f"Task workspace created: {workspace_dir}")
        return workspace_dir
        
    except Exception as e:
        logger.error(f"Failed to create task workspace: {str(e)}")
        return None


def cleanup_task_workspace(execution_id: UUID) -> bool:
    """清理任务工作空间"""
    try:
        workspace_dir = f"/tmp/task_workspaces/{execution_id}"
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)
            logger.info(f"Cleaned up task workspace for execution {execution_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup task workspace: {str(e)}")
        return False


def validate_task_config(config_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """验证任务配置"""
    try:
        required_fields = ["task_name", "task_type", "base_url"]
        
        for field in required_fields:
            if field not in config_data:
                return False, f"Missing required field: {field}"
        
        # 验证任务类型
        valid_types = ["docker-crawl", "api", "database"]
        if config_data.get("task_type") not in valid_types:
            return False, f"Invalid task type: {config_data.get('task_type')}"
        
        # 验证 URL 格式
        base_url = config_data.get("base_url")
        if base_url and not base_url.startswith(("http://", "https://")):
            return False, "Invalid base URL format"
        
        return True, None
        
    except Exception as e:
        return False, f"Config validation error: {str(e)}"


def upload_config_to_remote_machine(local_config_file: str, execution_id: UUID) -> str:
    """上传配置文件到远程执行机器"""
    try:
        # 远程机器上的配置目录
        remote_config_dir = f"/tmp/task_configs/{execution_id}"
        remote_config_file = f"{remote_config_dir}/config.json"
        
        # 创建远程配置目录
        mkdir_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "mkdir", "-p", remote_config_dir
        ]
        
        subprocess.run(mkdir_command, check=True, timeout=30)
        logger.info(f"Created remote config directory: {remote_config_dir}")
        
        # 上传配置文件
        scp_command = [
            "scp", "-o", "StrictHostKeyChecking=no",
            local_config_file,
            f"root@{settings.DOCKER_HOST_IP}:{remote_config_file}"
        ]
        
        subprocess.run(scp_command, check=True, timeout=60)
        logger.info(f"Uploaded config file to remote machine: {remote_config_file}")
        
        return remote_config_file
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to upload config file: {e}")
        raise Exception(f"配置文件上传失败: {e}")
    except subprocess.TimeoutExpired:
        logger.error("Config file upload timeout")
        raise Exception("配置文件上传超时")
    except Exception as e:
        logger.error(f"Unexpected error during config upload: {e}")
        raise


def start_docker_task_container(execution_id: UUID, docker_image: str, config_path: str, 
                            additional_volumes: Optional[Dict[str, str]] = None) -> str:
    """启动Docker任务容器"""
    try:
        container_name = f"task-{execution_id}"
        
        # 检查是否为本地环境（DOCKER_HOST_IP为localhost或127.0.0.1）
        if settings.DOCKER_HOST_IP in ["localhost", "127.0.0.1", "0.0.0.0"]:
            # 本地环境，直接使用docker命令
            docker_command = [
                "docker", "run", "-d",
                "--name", container_name,
                "--rm",  # 自动清理容器
            ]
        else:
            # 远程环境，使用SSH
            docker_command = [
                "ssh", f"root@{settings.DOCKER_HOST_IP}",
                "docker", "run", "-d",
                "--name", container_name,
                "--rm",  # 自动清理容器
            ]
        
        # 添加配置文件挂载
        docker_command.extend([
            "-v", f"{config_path}:/app/config/config.json:ro"
        ])
        
        # 添加额外的卷挂载
        if additional_volumes:
            for host_path, container_path in additional_volumes.items():
                docker_command.extend(["-v", f"{host_path}:{container_path}"])
        
        # 添加环境变量
        docker_command.extend([
            "-e", f"TASK_EXECUTION_ID={execution_id}",
            "-e", "CONFIG_PATH=/app/config/config.json"
        ])
        
        # 添加Docker镜像
        docker_command.append(docker_image)
        
        # 执行Docker命令
        result = subprocess.run(docker_command, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            container_id = result.stdout.strip()
            logger.info(f"Docker task container started: {container_name} ({container_id})")
            return container_id
        else:
            logger.error(f"Failed to start Docker container: {result.stderr}")
            raise Exception(f"Docker容器启动失败: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error("Docker container start timeout")
        raise Exception("Docker容器启动超时")
    except Exception as e:
        logger.error(f"Failed to start Docker container: {e}")
        raise


def stop_docker_task_container(container_id: str) -> bool:
    """停止Docker任务容器"""
    try:
        stop_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "docker", "stop", container_id
        ]
        
        result = subprocess.run(stop_command, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info(f"Docker task container stopped: {container_id}")
            return True
        else:
            logger.error(f"Failed to stop Docker container: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error stopping Docker container: {e}")
        return False


def cleanup_remote_config_files(execution_id: UUID) -> bool:
    """清理远程配置文件"""
    try:
        remote_config_dir = f"/tmp/task_configs/{execution_id}"
        
        cleanup_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "rm", "-rf", remote_config_dir
        ]
        
        subprocess.run(cleanup_command, timeout=30)
        logger.info(f"Cleaned up remote config files: {remote_config_dir}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to cleanup remote config files: {e}")
        return False


def get_docker_container_logs(container_id: str, lines: int = 100) -> Optional[str]:
    """获取Docker容器日志"""
    try:
        logs_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "docker", "logs", "--tail", str(lines), container_id
        ]
        
        result = subprocess.run(logs_command, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return result.stdout
        else:
            logger.error(f"Failed to get container logs: {result.stderr}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting container logs: {e}")
        return None
