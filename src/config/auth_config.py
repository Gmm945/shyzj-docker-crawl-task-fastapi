import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


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
    DATABASE_URL: str = os.getenv("DATABASE_URL", "mysql+aiomysql://app_user:123456@localhost:3306/data_platform")
    DATABASE_DB_NAME: str = os.getenv("DATABASE_DB_NAME", "data_platform")
    
    # Redis配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    
    # Celery配置
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Docker配置
    DOCKER_HOST: str = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    
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
    
    # 安全配置
    ALLOWED_HOSTS: str = os.getenv("ALLOWED_HOSTS", "*")
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # 秒
    
    # Docker配置
    DOCKER_HOST_IP: str = os.getenv("DOCKER_HOST_IP", "192.168.1.100")
    DOCKER_IMAGE: str = os.getenv("DOCKER_IMAGE", "data-platform-crawler:latest")
    DOCKER_CONFIG_PATH: str = os.getenv("DOCKER_CONFIG_PATH", "/app/configs")
    HEARTBEAT_REDUNDANCY: int = int(os.getenv("HEARTBEAT_REDUNDANCY", "60"))  # 心跳冗余时间（秒）
    
    # 管理员配置
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    class Config:
        """
        Config class
        """
        case_sensitive = True


settings = AuthSettings()
