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

    # Docker配置
    DOCKER_HOST: str = get_env("DOCKER_HOST")
    DOCKER_CRAWLER_IMAGE: str = get_env("DOCKER_CRAWLER_IMAGE")
    DOCKER_API_IMAGE: str = os.getenv("DOCKER_API_IMAGE", "data-collection-api:latest")
    DOCKER_DATABASE_IMAGE: str = os.getenv("DOCKER_DATABASE_IMAGE", "data-collection-database:latest")
    CONTAINER_SERVICE_PORT: int = int(get_env("CONTAINER_SERVICE_PORT"))
    DOCKER_AUTO_REMOVE: bool = os.getenv("DOCKER_AUTO_REMOVE", "False").lower() == "true"  # 运行结束是否自动删除容器
    DOCKER_REMOVE_ON_STOP: bool = os.getenv("DOCKER_REMOVE_ON_STOP", "False").lower() == "true"  # stop 接口是否删除容器
    SSH_USER: str = get_env("SSH_USER")  # SSH登录用户名
    # API 访问配置（供容器心跳回调使用）
    API_PORT: int = int(get_env("API_PORT"))
    API_BASE_URL: str = get_env("API_BASE_URL")  # 留空则按 DOCKER_HOST_IP/API_PORT

    # 任务配置
    MAX_CONCURRENT_TASKS: int = int(os.getenv("MAX_CONCURRENT_TASKS", "10"))
    TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "3600"))  # 1小时
    HEARTBEAT_TIMEOUT: int = int(os.getenv("HEARTBEAT_TIMEOUT", "300"))  # 5分钟

    # 文件存储配置
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "100"))  # MB

    # 监控配置
    MONITORING_ENABLED: bool = os.getenv("MONITORING_ENABLED", "True").lower() == "true"
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9090"))
    MONITOR_CHECK_INTERVAL: int = int(os.getenv("MONITOR_CHECK_INTERVAL", "30"))  # 任务监控轮询间隔（秒）
    # 时区配置
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Shanghai")

    # 安全配置
    ALLOWED_HOSTS: str = os.getenv("ALLOWED_HOSTS", "*")
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # 秒

    # Docker配置
    DOCKER_HOST_IP: str = get_env("DOCKER_HOST_IP")
    DOCKER_CONFIG_PATH: str = os.getenv("DOCKER_CONFIG_PATH", "/app/configs")
    HEARTBEAT_REDUNDANCY: int = int(os.getenv("HEARTBEAT_REDUNDANCY", "60"))  # 心跳冗余时间（秒）
    PORT_RANGE_START: int = int(os.getenv("PORT_RANGE_START", "50001"))
    PORT_RANGE_END: int = int(os.getenv("PORT_RANGE_END", "50100"))

    # 管理员配置
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    class Config:
        """
        Config class
        """
        case_sensitive = True


settings = AuthSettings()
