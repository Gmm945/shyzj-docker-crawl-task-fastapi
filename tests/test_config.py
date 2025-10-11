"""
测试配置文件
============

这个文件包含了测试脚本的配置信息，包括：
- 服务器地址和端口
- 测试用户信息
- 测试任务配置
- 超时设置等

可以通过修改这个文件来调整测试参数。
"""

import os
from typing import Dict, Any


class TestConfig:
    """测试配置类"""
    
    # 服务器配置
    BASE_URL: str = os.getenv("TEST_BASE_URL", "http://localhost:8000")
    TIMEOUT: int = int(os.getenv("TEST_TIMEOUT", "30"))
    
    # 管理员账户配置
    ADMIN_USERNAME: str = os.getenv("TEST_ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("TEST_ADMIN_PASSWORD", "admin123")
    
    # 测试用户配置
    TEST_USER_PREFIX: str = os.getenv("TEST_USER_PREFIX", "test_user")
    TEST_USER_PASSWORD: str = os.getenv("TEST_USER_PASSWORD", "TestPassword123!")
    TEST_USER_EMAIL_DOMAIN: str = os.getenv("TEST_USER_EMAIL_DOMAIN", "example.com")
    
    # 测试任务配置
    TEST_TASK_CONFIGS: Dict[str, Dict[str, Any]] = {
        "api_task": {
            "task_type": "api",
            "base_url": "https://httpbin.org/json",
            "base_url_params": [],
            "need_user_login": 0,
            "extract_config": {
                "extract_method": "api",
                "listened_uri": "/json",
                "extract_dataset_idtf": "test_data",
                "extract_fields": []
            },
            "description": "API测试任务"
        },
        "docker_crawl_task": {
            "task_type": "docker-crawl",
            "base_url": "https://httpbin.org/json",
            "base_url_params": [],
            "need_user_login": 0,
            "extract_config": {
                "extract_method": "api",
                "listened_uri": "/json",
                "extract_dataset_idtf": "test_data",
                "extract_fields": []
            },
            "description": "Docker爬虫测试任务"
        },
        "database_task": {
            "task_type": "database",
            "base_url": "localhost:3306",
            "base_url_params": [],
            "need_user_login": 0,
            "extract_config": {
                "extract_method": "api",
                "listened_uri": "",
                "extract_dataset_idtf": "test_data",
                "extract_fields": []
            },
            "description": "数据库测试任务"
        }
    }
    
    # 调度配置
    SCHEDULE_CONFIGS: Dict[str, Dict[str, Any]] = {
        "immediate": {
            "schedule_type": "immediate",
            "schedule_config": {}
        },
        "cron": {
            "schedule_type": "scheduled",
            "schedule_config": {
                "cron_expression": "*/5 * * * *",  # 每5分钟执行一次
                "timezone": "Asia/Shanghai"
            }
        },
        "interval": {
            "schedule_type": "interval",
            "schedule_config": {
                "seconds": 300  # 每5分钟执行一次
            }
        }
    }
    
    # 测试数据配置
    TEST_DATA: Dict[str, Any] = {
        "cleanup_after_test": True,  # 测试后是否清理数据
        "max_execution_time": 120,   # 最大执行时间（秒）
        "retry_count": 3,            # 重试次数
        "retry_delay": 5             # 重试延迟（秒）
    }
    
    # 日志配置
    LOG_CONFIG: Dict[str, Any] = {
        "level": "INFO",
        "format": "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        "colorize": True
    }
    
    @classmethod
    def get_test_user_data(cls, suffix: str = None) -> Dict[str, str]:
        """获取测试用户数据"""
        import time
        
        if suffix is None:
            suffix = str(int(time.time()))
        
        return {
            "username": f"{cls.TEST_USER_PREFIX}_{suffix}",
            "email": f"{cls.TEST_USER_PREFIX}_{suffix}@{cls.TEST_USER_EMAIL_DOMAIN}",
            "password": cls.TEST_USER_PASSWORD,
            "full_name": f"测试用户_{suffix}"
        }
    
    @classmethod
    def get_test_task_data(cls, task_type: str, suffix: str = None) -> Dict[str, Any]:
        """获取测试任务数据"""
        import time
        
        if suffix is None:
            suffix = str(int(time.time()))
        
        if task_type not in cls.TEST_TASK_CONFIGS:
            raise ValueError(f"未知的任务类型: {task_type}")
        
        base_config = cls.TEST_TASK_CONFIGS[task_type].copy()
        base_config["task_name"] = f"测试{task_type}任务_{suffix}"
        base_config["description"] = f"这是一个测试用的{task_type}任务"
        
        return base_config
    
    @classmethod
    def get_test_schedule_data(cls, schedule_type: str, task_id: str) -> Dict[str, Any]:
        """获取测试调度数据"""
        if schedule_type not in cls.SCHEDULE_CONFIGS:
            raise ValueError(f"未知的调度类型: {schedule_type}")
        
        schedule_data = cls.SCHEDULE_CONFIGS[schedule_type].copy()
        schedule_data["task_id"] = task_id
        schedule_data["is_active"] = True
        
        return schedule_data


# 全局配置实例
config = TestConfig()
