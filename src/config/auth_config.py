import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


def get_env(env):
    try:
        return os.environ[env]
    except Exception as e:
        raise ValueError(f"读取 {env} 出错，请检查.envw文件")


class AuthSettings(BaseSettings):
    """
    认证和系统设置类
    """
    # 认证相关
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 300))  # 默认5小时
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'data-platform-secret-key')
    ALGORITHM: str = os.getenv('ALGORITHM', 'HS256')

    # 认证开关 - 设置为 False 可以一键关闭所有认证
    ENABLE_AUTH: bool = os.getenv('ENABLE_AUTH', 'True').lower() == 'true'

    # 应用配置
    APP_CORS: str = os.getenv("APP_CORS", "")
    APP_SECRET_KEY: str = os.getenv("APP_SECRET_KEY", "data-platform-app-secret")
    APP_FRONT_URI: str = os.getenv("APP_FRONT_URI", "")
    APP_CORS_ALLOW_ORIGINS: str = os.getenv("APP_CORS_ALLOW_ORIGINS", "")

    # 数据库配置
    DATABASE_URL: str = get_env("DATABASE_URL")
    DATABASE_DB_NAME: str = get_env("DATABASE_DB_NAME")

    # Redis配置
    REDIS_URL: str = get_env("REDIS_URL")
    REDIS_HOST: str = get_env("REDIS_HOST")
    REDIS_PORT: int = int(get_env("REDIS_PORT"))
    REDIS_DB: int = int(get_env("REDIS_DB"))
    REDIS_PASSWORD: str = get_env("REDIS_PASSWORD")

    # Celery配置
    CELERY_BROKER_URL: str = get_env("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = get_env("CELERY_RESULT_BACKEND")

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # 远程Docker配置
    DOCKER_HOST: str = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    DOCKER_HOST_IP: str = os.getenv("DOCKER_HOST_IP", "localhost")  # Docker主机IP
    SSH_USER: str = os.getenv("SSH_USER", "root")  # SSH登录用户名
    DOCKER_AUTO_REMOVE: bool = os.getenv("DOCKER_AUTO_REMOVE", "False").lower() == "true"  # 运行结束是否自动删除容器
    DOCKER_REMOVE_ON_STOP: bool = os.getenv("DOCKER_REMOVE_ON_STOP", "False").lower() == "true"  # stop 接口是否删除容器
    DOCKER_CONFIG_PATH: str = os.getenv("DOCKER_CONFIG_PATH", "/app/configs")
    
    # 任务Docker镜像配置
    DOCKER_CRAWLER_IMAGE: str = os.getenv("DOCKER_CRAWLER_IMAGE", "crawler-service:latest")
    DOCKER_API_IMAGE: str = os.getenv("DOCKER_API_IMAGE", "data-collection-api:latest")
    DOCKER_DATABASE_IMAGE: str = os.getenv("DOCKER_DATABASE_IMAGE", "data-collection-database:latest")
    
    # 主服务端口配置
    API_PORT: int = int(os.getenv("API_PORT", "8000"))  # API服务端口
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9090"))  # 监控端口
    # 远程docker服务端口范围
    PORT_RANGE_START: int = int(os.getenv("PORT_RANGE_START", "50001"))  # 容器端口范围开始
    PORT_RANGE_END: int = int(os.getenv("PORT_RANGE_END", "50100"))  # 容器端口范围结束
    
    # 主服务API访问配置（供容器心跳回调使用）
    API_BASE_URL: str = os.getenv("API_BASE_URL", "")  # 自定义API基础URL，留空则自动生成
    # 任务配置
    MAX_CONCURRENT_TASKS: int = int(os.getenv("MAX_CONCURRENT_TASKS", "10"))
    TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "3600"))  # 1小时
    HEARTBEAT_TIMEOUT: int = int(os.getenv("HEARTBEAT_TIMEOUT", "300"))  # 5分钟

    # 文件存储配置
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "100"))  # MB

    # 监控配置
    MONITORING_ENABLED: bool = os.getenv("MONITORING_ENABLED", "True").lower() == "true"
    MONITOR_CHECK_INTERVAL: int = int(os.getenv("MONITOR_CHECK_INTERVAL", "30"))  # 任务监控轮询间隔（秒）
    HEARTBEAT_REDUNDANCY: int = int(os.getenv("HEARTBEAT_REDUNDANCY", "60"))  # 心跳冗余时间（秒）
    
    # 时区配置
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Shanghai")

    # 安全配置
    ALLOWED_HOSTS: str = os.getenv("ALLOWED_HOSTS", "*")
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # 秒
    # 管理员配置
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    
    @property
    def effective_api_base_url(self) -> str:
        """获取有效的API基础URL"""
        if self.API_BASE_URL:
            return self.API_BASE_URL.rstrip('/')
        
        # 自动生成API基础URL
        is_local = self.DOCKER_HOST_IP in ["localhost", "127.0.0.1", "0.0.0.0"]
        if is_local:
            return f"http://host.docker.internal:{self.API_PORT}"
        else:
            return f"http://{self.DOCKER_HOST_IP}:{self.API_PORT}"
    
    @property
    def is_local_docker(self) -> bool:
        """判断是否为本地Docker环境"""
        return self.DOCKER_HOST_IP in ["localhost", "127.0.0.1", "0.0.0.0"]

    class Config:
        """
        Config class
        """
        case_sensitive = True


settings = AuthSettings()
