"""
Docker 容器管理相关任务
"""
import subprocess
from datetime import datetime, timedelta
from loguru import logger

from .celeryconfig import celery_app
from .utils.task_progress_util import BaseTaskWithProgress
from .db_tasks import get_task_execution_by_id
from ..config.auth_config import settings


def stop_docker_container_impl(self, container_id: str, namespace: str = "docker_management"):
    """停止Docker容器实现"""
    try:
        self.update_status(0, "PENDING", "开始停止容器", namespace=namespace)
        
        # 停止容器
        stop_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "docker", "stop", container_id
        ]
        
        result = subprocess.run(stop_command, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info(f"容器停止成功: {container_id}")
            
            # 删除容器
            rm_command = [
                "ssh", f"root@{settings.DOCKER_HOST_IP}",
                "docker", "rm", container_id
            ]
            subprocess.run(rm_command, capture_output=True, text=True)
            logger.info(f"容器删除成功: {container_id}")
            
            self.update_status(100, "SUCCESS", "容器停止成功", namespace=namespace)
            return {"success": True, "message": "容器停止成功"}
        else:
            logger.error(f"停止容器失败: {container_id}, {result.stderr}")
            self.update_status(0, "FAILURE", f"停止容器失败: {result.stderr}", namespace=namespace)
            return {"success": False, "message": result.stderr}
            
    except Exception as e:
        logger.error(f"停止容器异常: {container_id}, {e}")
        self.update_status(0, "FAILURE", f"停止容器异常: {str(e)}", namespace=namespace)
        raise


def kill_docker_container_impl(
    self,
    container_id: str,
    namespace: str = "docker_management"
):
    """强制杀死Docker容器"""
    try:
        self.update_status(0, "PENDING", "开始强制杀死容器", namespace=namespace)
        
        # 强制杀死容器
        kill_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "docker", "kill", container_id
        ]
        
        result = subprocess.run(kill_command, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            logger.info(f"容器强制杀死成功: {container_id}")
            
            # 删除容器
            rm_command = [
                "ssh", f"root@{settings.DOCKER_HOST_IP}",
                "docker", "rm", "-f", container_id
            ]
            subprocess.run(rm_command, capture_output=True, text=True)
            
            self.update_status(100, "SUCCESS", "容器强制杀死成功", namespace=namespace)
            return {"success": True, "message": "容器强制杀死成功"}
        else:
            logger.error(f"强制杀死容器失败: {container_id}, {result.stderr}")
            self.update_status(0, "FAILURE", f"强制杀死容器失败: {result.stderr}", namespace=namespace)
            return {"success": False, "message": result.stderr}
            
    except Exception as e:
        logger.error(f"强制杀死容器异常: {container_id}, {e}")
        self.update_status(0, "FAILURE", f"强制杀死容器异常: {str(e)}", namespace=namespace)
        raise


def get_container_status_impl(
    self,
    container_id: str,
    namespace: str = "docker_management"
):
    """获取容器状态"""
    try:
        self.update_status(0, "PENDING", "获取容器状态", namespace=namespace)
        
        # 获取容器状态
        inspect_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "docker", "inspect", "--format", 
            "{{.State.Status}}|{{.State.ExitCode}}|{{.State.Running}}", 
            container_id
        ]
        
        result = subprocess.run(inspect_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            status_info = result.stdout.strip().split("|")
            status_data = {
                "status": status_info[0],
                "exit_code": int(status_info[1]) if status_info[1] != "<no value>" else None,
                "running": status_info[2] == "true",
                "exists": True
            }
            self.update_status(100, "SUCCESS", "获取容器状态成功", namespace=namespace)
            return status_data
        else:
            status_data = {"exists": False, "status": "not_found"}
            self.update_status(100, "SUCCESS", "容器不存在", namespace=namespace)
            return status_data
            
    except Exception as e:
        logger.error(f"获取容器状态异常: {container_id}, {e}")
        self.update_status(0, "FAILURE", f"获取容器状态异常: {str(e)}", namespace=namespace)
        return {"exists": False, "status": "error", "error": str(e)}


def get_container_logs_impl(
    self,
    container_id: str,
    lines: int = 100,
    namespace: str = "docker_management"
):
    """获取容器日志"""
    try:
        self.update_status(0, "PENDING", "获取容器日志", namespace=namespace)
        
        # 获取容器日志
        logs_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "docker", "logs", "--tail", str(lines), container_id
        ]
        
        result = subprocess.run(logs_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"获取容器日志成功: {container_id}")
            self.update_status(100, "SUCCESS", "获取容器日志成功", namespace=namespace)
            return {"success": True, "logs": result.stdout}
        else:
            logger.error(f"获取容器日志失败: {container_id}, {result.stderr}")
            self.update_status(0, "FAILURE", f"获取容器日志失败: {result.stderr}", namespace=namespace)
            return {"success": False, "message": result.stderr}
            
    except Exception as e:
        logger.error(f"获取容器日志异常: {container_id}, {e}")
        self.update_status(0, "FAILURE", f"获取容器日志异常: {str(e)}", namespace=namespace)
        return {"success": False, "message": str(e)}


def cleanup_old_containers_impl(
    self,
    namespace: str = "cleanup"
):
    """清理旧的容器"""
    try:
        self.update_status(0, "PENDING", "开始清理旧容器", namespace=namespace)
        
        # 清理停止的容器
        cleanup_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "docker", "container", "prune", "-f"
        ]
        
        result = subprocess.run(cleanup_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("清理旧容器成功")
            self.update_status(100, "SUCCESS", "清理旧容器成功", namespace=namespace)
            return {"success": True, "message": "清理旧容器成功"}
        else:
            logger.error(f"清理旧容器失败: {result.stderr}")
            self.update_status(0, "FAILURE", f"清理旧容器失败: {result.stderr}", namespace=namespace)
            return {"success": False, "message": result.stderr}
            
    except Exception as e:
        logger.error(f"清理旧容器异常: {e}")
        self.update_status(0, "FAILURE", f"清理旧容器异常: {str(e)}", namespace=namespace)
        raise


def cleanup_old_configs_impl(
    self,
    namespace: str = "cleanup"
):
    """清理旧的配置文件"""
    try:
        self.update_status(0, "PENDING", "开始清理旧配置文件", namespace=namespace)
        
        # 清理临时配置文件
        cleanup_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "find", "/tmp/task_configs", "-type", "f", "-mtime", "+1", "-delete"
        ]
        
        result = subprocess.run(cleanup_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("清理旧配置文件成功")
            self.update_status(100, "SUCCESS", "清理旧配置文件成功", namespace=namespace)
            return {"success": True, "message": "清理旧配置文件成功"}
        else:
            logger.error(f"清理旧配置文件失败: {result.stderr}")
            self.update_status(0, "FAILURE", f"清理旧配置文件失败: {result.stderr}", namespace=namespace)
            return {"success": False, "message": result.stderr}
            
    except Exception as e:
        logger.error(f"清理旧配置文件异常: {e}")
        self.update_status(0, "FAILURE", f"清理旧配置文件异常: {str(e)}", namespace=namespace)
        raise


def check_docker_host_connection_impl(
    self,
    namespace: str = "health_check"
):
    """检查Docker主机连接"""
    try:
        self.update_status(0, "PENDING", "检查Docker主机连接", namespace=namespace)
        
        # 检查SSH连接
        ssh_command = [
            "ssh", f"root@{settings.DOCKER_HOST_IP}",
            "echo", "connection_test"
        ]
        
        result = subprocess.run(ssh_command, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "connection_test" in result.stdout:
            logger.info("Docker主机连接正常")
            self.update_status(100, "SUCCESS", "Docker主机连接正常", namespace=namespace)
            return {"success": True, "message": "Docker主机连接正常"}
        else:
            logger.error(f"Docker主机连接失败: {result.stderr}")
            self.update_status(0, "FAILURE", f"Docker主机连接失败: {result.stderr}", namespace=namespace)
            return {"success": False, "message": result.stderr}
            
    except Exception as e:
        logger.error(f"检查Docker主机连接异常: {e}")
        self.update_status(0, "FAILURE", f"检查Docker主机连接异常: {str(e)}", namespace=namespace)
        raise


# 非Celery任务的辅助函数
def monitor_container(container_id: str, execution_id: str):
    """监控容器状态（非Celery任务）"""
    try:
        # 直接调用实现函数
        result = get_container_status_impl.delay(container_id)
        status = result.get()
        
        if not status.get("exists", False):
            logger.warning(f"容器不存在: {container_id}")
            return False
            
        if not status.get("running", False):
            logger.info(f"容器已停止: {container_id}")
            return False
            
        logger.debug(f"容器运行正常: {container_id}")
        return True
        
    except Exception as e:
        logger.error(f"监控容器异常: {container_id}, {e}")
        return False


def cleanup_container(container_id: str):
    """清理容器（非Celery任务）"""
    try:
        # 停止并删除容器
        stop_docker_container_impl.delay(container_id)
        logger.info(f"容器清理任务已提交: {container_id}")
        return True
        
    except Exception as e:
        logger.error(f"清理容器异常: {container_id}, {e}")
        return False


def check_heartbeat_timeout(execution_id: str, timeout_minutes: int = 30):
    """检查心跳超时（非Celery任务）"""
    try:
        execution = get_task_execution_by_id(execution_id)
        if not execution:
            return False
            
        if not execution.last_heartbeat:
            return True  # 没有心跳记录，认为超时
            
        timeout_threshold = datetime.now() - timedelta(minutes=timeout_minutes)
        return execution.last_heartbeat < timeout_threshold
        
    except Exception as e:
        logger.error(f"检查心跳超时异常: {execution_id}, {e}")
        return True  # 异常情况下认为超时
