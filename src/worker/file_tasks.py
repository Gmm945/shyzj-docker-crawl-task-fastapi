import os
import json
import shutil
import subprocess
from typing import Dict, Any, Optional
import socket
from uuid import UUID
from loguru import logger
from datetime import datetime

from .db import make_sync_session
from .db_tasks import update_task_execution_status, get_task_execution_by_id
from ..data_platform_api.models.task import TaskExecution
from ..config.auth_config import settings
from .db_tasks import update_task_execution_docker_info

# 端口使用缓存（单次进程内，避免重复尝试同端口）
_USED_PORTS_CACHE: set[int] = set()


def check_ssh_connection(host: str, user: str = None) -> bool:
    """检查SSH免密登录是否配置成功"""
    if user is None:
        user = settings.SSH_USER
    
    try:
        # 使用ssh命令测试连接，超时时间设置为10秒
        test_command = [
            "ssh", "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",  # 禁用交互式认证
            "-o", "StrictHostKeyChecking=no",
            f"{user}@{host}",
            "echo 'SSH connection successful'"
        ]
        
        result = subprocess.run(test_command, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            logger.info(f"SSH免密登录检查成功: {user}@{host}")
            return True
        else:
            logger.error(f"SSH免密登录失败: {user}@{host}")
            logger.error(f"错误信息: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"SSH连接超时: {user}@{host}")
        return False
    except Exception as e:
        logger.error(f"SSH连接检查异常: {e}")
        return False


def get_ssh_host_string(host: str, user: str = None) -> str:
    """获取SSH连接字符串"""
    if user is None:
        user = settings.SSH_USER
    return f"{user}@{host}"


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
        # 如果是本地Docker主机，直接返回本地配置文件路径（无需SSH）
        if settings.is_local_docker:
            logger.info("本地环境检测到，跳过SSH上传，使用本地配置文件")
            return local_config_file

        # 远程机器上的配置目录
        remote_config_dir = f"/tmp/task_configs/{execution_id}"
        remote_config_file = f"{remote_config_dir}/config.json"
        
        # 检查SSH免密登录是否配置成功
        logger.info(f"检查SSH免密登录配置: {settings.SSH_USER}@{settings.DOCKER_HOST_IP}")
        if not check_ssh_connection(settings.DOCKER_HOST_IP, settings.SSH_USER):
            error_msg = (
                f"SSH免密登录配置失败！\n"
                f"请确保已配置SSH免密登录到 {settings.SSH_USER}@{settings.DOCKER_HOST_IP}\n"
                f"配置方法：\n"
                f"1. 生成SSH密钥对：ssh-keygen -t rsa\n"
                f"2. 复制公钥到远程主机：ssh-copy-id {settings.SSH_USER}@{settings.DOCKER_HOST_IP}\n"
                f"3. 测试连接：ssh {settings.SSH_USER}@{settings.DOCKER_HOST_IP}\n"
                f"或者通过环境变量 SSH_USER 指定其他用户名"
            )
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 创建远程配置目录
        ssh_host = get_ssh_host_string(settings.DOCKER_HOST_IP, settings.SSH_USER)
        mkdir_command = [
            "ssh", ssh_host,
            "mkdir", "-p", remote_config_dir
        ]
        
        subprocess.run(mkdir_command, check=True, timeout=30)
        logger.info(f"Created remote config directory: {remote_config_dir}")
        
        # 上传配置文件
        scp_command = [
            "scp", "-o", "StrictHostKeyChecking=no",
            local_config_file,
            f"{ssh_host}:{remote_config_file}"
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


def _is_remote_port_listening(port: int) -> bool:
    """检测远程主机端口是否被占用（监听中）。
    优先使用 ss，其次使用 netstat，最后尝试 lsof。
    返回 True 表示端口被占用。
    """
    ssh_host = get_ssh_host_string(settings.DOCKER_HOST_IP)
    check_cmds = [
        ["ssh", ssh_host, "bash", "-lc", f"ss -ltn | awk '{{print $4}}' | grep -E ':{port}$' | wc -l"],
        ["ssh", ssh_host, "bash", "-lc", f"netstat -ltn 2>/dev/null | awk '{{print $4}}' | grep -E ':{port}$' | wc -l"],
        ["ssh", ssh_host, "bash", "-lc", f"lsof -iTCP:{port} -sTCP:LISTEN | wc -l"],
    ]
    for cmd in check_cmds:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if result.returncode == 0:
                count_str = (result.stdout or "").strip()
                try:
                    count = int(count_str)
                except ValueError:
                    continue
                if count > 0:
                    return True
                return False
        except Exception:
            continue
    # 无法检测，保守认为被占用，由上层重试
    return True


def _mark_port_as_used_once(port: Optional[int]) -> None:
    if port is None:
        return
    _USED_PORTS_CACHE.add(port)


def start_docker_task_container(execution_id: UUID, docker_image: str, config_path: str, 
                            additional_volumes: Optional[Dict[str, str]] = None) -> str:
    """启动Docker任务容器"""
    try:
        container_name = f"task-{execution_id}"
        
        # 构建 Docker 命令
        if settings.is_local_docker:
            # 本地环境，直接使用docker命令
            base_command = [
                "docker", "run", "-d",
                "--name", container_name,
                "--hostname", container_name,
                *( ["--rm"] if settings.DOCKER_AUTO_REMOVE else [] ),
            ]
            # 让容器内可访问宿主：host.docker.internal（Linux 需以下参数；mac/Win原生支持）
            base_command.extend(["--add-host", "host.docker.internal:host-gateway"])
        else:
            # 远程环境，使用SSH
            base_command = [
                "ssh", get_ssh_host_string(settings.DOCKER_HOST_IP),
                "docker", "run", "-d",
                "--name", container_name,
                "--hostname", container_name,
                *( ["--rm"] if settings.DOCKER_AUTO_REMOVE else [] ),
            ]
        
        # 添加配置文件挂载
        base_command.extend([
            "-v", f"{config_path}:/app/config.json:ro"
        ])
        
        # 添加额外的卷挂载
        if additional_volumes:
            for host_path, container_path in additional_volumes.items():
                base_command.extend(["-v", f"{host_path}:{container_path}"])
        
        # 使用配置类自动生成的 API_BASE_URL
        api_base = settings.effective_api_base_url

        # 添加环境变量
        base_command.extend([
            "-e", f"TASK_EXECUTION_ID={execution_id}",
            "-e", "CONFIG_PATH=/app/config.json",
            "-e", f"API_BASE_URL={api_base}"
        ])
        
        # 端口映射：从配置的端口范围中选择可用端口；若冲突自动重试
        container_port = settings.CONTAINER_PORT  # 使用统一的API端口
        max_attempts = 5
        last_error: Optional[str] = None
        selected_host_port: Optional[int] = None
        for _ in range(max_attempts):
            host_port = _allocate_remote_port()
            selected_host_port = host_port
            docker_command = list(base_command)
            if host_port and container_port:
                docker_command.extend(["-p", f"{host_port}:{container_port}"])
            # 添加Docker镜像
            docker_command.append(docker_image)
            # 执行Docker命令
            result = subprocess.run(docker_command, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                container_id = result.stdout.strip()
                logger.info(f"Docker task container started: {container_name} ({container_id}) on port {host_port}")
                # 将端口号、容器名和Docker命令保存到执行记录中
                try:
                    docker_command_str = " ".join(docker_command)
                    update_task_execution_docker_info(
                        execution_id, 
                        port=host_port, 
                        container_name=container_name, 
                        container_id=container_id,
                        docker_command=docker_command_str
                    )
                    logger.info(f"Updated execution {execution_id} with Docker info: port={host_port}, container_name={container_name}, command saved")
                except Exception as e:
                    logger.error(f"Failed to update execution info: {e}")
                return container_id
            else:
                stderr = result.stderr or ""
                last_error = stderr
                # 遇到端口占用，尝试下一个端口
                if "port is already allocated" in stderr or "address already in use" in stderr.lower():
                    logger.warning(f"Port {host_port} is in use, retrying with next available port...")
                    # 标记该端口占用，避免下次再选到（通过远程检测实现）
                    _mark_port_as_used_once(host_port)
                    continue
                # 其他错误直接失败
                logger.error(f"Failed to start Docker container: {stderr}")
                raise Exception(f"Docker容器启动失败: {stderr}")
        # 超过重试次数
        err_msg = last_error or "端口分配失败"
        raise Exception(f"Docker容器启动失败: {err_msg}")
            
    except subprocess.TimeoutExpired:
        logger.error("Docker container start timeout")
        raise Exception("Docker容器启动超时")
    except Exception as e:
        logger.error(f"Failed to start Docker container: {e}")
        raise


def _allocate_remote_port() -> Optional[int]:
    """在远程或本机分配可用端口，支持远程探测并跳过缓存中已用端口。"""
    start = settings.PORT_RANGE_START
    end = settings.PORT_RANGE_END
    host = settings.DOCKER_HOST_IP
    if settings.is_local_docker:
        for port in range(start, end + 1):
            if port in _USED_PORTS_CACHE:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", port))
                    _USED_PORTS_CACHE.add(port)
                    return port
                except OSError:
                    continue
        return None
    else:
        # 远程主机：通过 ssh 在远端检测端口是否可用
        for port in range(start, end + 1):
            if port in _USED_PORTS_CACHE:
                continue
            if not _is_remote_port_listening(port):
                _USED_PORTS_CACHE.add(port)
                return port
        return None


def _mark_port_as_used_once(port: Optional[int]) -> None:
    if port is None:
        return
    _USED_PORTS_CACHE.add(port)


def stop_docker_task_container(container_id: str) -> bool:
    """停止Docker任务容器"""
    try:
        stop_command = [
            "ssh", get_ssh_host_string(settings.DOCKER_HOST_IP),
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
            "ssh", get_ssh_host_string(settings.DOCKER_HOST_IP),
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
        # 本地环境直接使用docker命令，远程环境使用SSH
        if settings.is_local_docker:
            logs_command = ["docker", "logs", "--tail", str(lines), container_id]
        else:
            logs_command = [
                "ssh", get_ssh_host_string(settings.DOCKER_HOST_IP),
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


def get_docker_container_status(container_id: str) -> Optional[dict]:
    """获取Docker容器状态（本地优先，远程通过SSH）。
    返回: {"exists": bool, "running": bool, "status": str}
    """
    try:
        if settings.is_local_docker:
            cmd = [
                "docker", "inspect", "--format",
                "{{.State.Status}}|{{.State.Running}}",
                container_id,
            ]
        else:
            cmd = [
                "ssh", get_ssh_host_string(settings.DOCKER_HOST_IP),
                "docker", "inspect", "--format",
                "{{.State.Status}}|{{.State.Running}}",
                container_id,
            ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode != 0:
            return {"exists": False, "running": False, "status": "not_found"}
        status_str = result.stdout.strip()
        parts = status_str.split("|")
        status = parts[0] if parts else "unknown"
        running = (parts[1].lower() == "true") if len(parts) > 1 else False
        return {"exists": True, "running": running, "status": status}
    except Exception as e:
        logger.error(f"Get container status error: {e}")
        return {"exists": False, "running": False, "status": "error"}
