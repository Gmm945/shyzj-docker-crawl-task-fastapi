"""
测试工具模块
============

这个模块提供了测试脚本中常用的工具函数，包括：
- HTTP客户端封装
- 用户认证管理
- 测试数据生成
- 结果验证工具
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from uuid import uuid4

import httpx
from loguru import logger

from .test_config import config


class TestHTTPClient:
    """测试用HTTP客户端"""
    
    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = base_url or config.BASE_URL
        self.timeout = timeout or config.TIMEOUT
        self.client = httpx.AsyncClient(timeout=self.timeout)
        self.access_token: Optional[str] = None
        self.user_id: Optional[str] = None
    
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        
        # 添加认证头
        if self.access_token:
            headers = kwargs.get('headers', {})
            headers['Authorization'] = f'Bearer {self.access_token}'
            kwargs['headers'] = headers
        
        try:
            response = await self.client.request(method, url, **kwargs)
            return response
        except httpx.HTTPError as e:
            logger.error(f"HTTP请求失败: {e}")
            raise
    
    async def get(self, endpoint: str, **kwargs) -> httpx.Response:
        """GET请求"""
        return await self.request("GET", endpoint, **kwargs)
    
    async def post(self, endpoint: str, **kwargs) -> httpx.Response:
        """POST请求"""
        return await self.request("POST", endpoint, **kwargs)
    
    async def put(self, endpoint: str, **kwargs) -> httpx.Response:
        """PUT请求"""
        return await self.request("PUT", endpoint, **kwargs)
    
    async def delete(self, endpoint: str, **kwargs) -> httpx.Response:
        """DELETE请求"""
        return await self.request("DELETE", endpoint, **kwargs)


class AuthManager:
    """认证管理器"""
    
    def __init__(self, client: TestHTTPClient):
        self.client = client
        self.admin_token = None
    
    async def init_admin(self) -> bool:
        """初始化管理员账户"""
        logger.info("🔐 初始化管理员账户...")
        
        try:
            response = await self.client.post("/api/v1/user/init-admin")
            
            if response.status_code == 200:
                admin_data = response.json()
                logger.success(f"✅ 管理员账户创建成功: {admin_data}")
                return True
            elif response.status_code == 400:
                logger.info("ℹ️ 管理员账户已存在")
                return True
            else:
                logger.warning(f"⚠️ 管理员账户初始化失败: {response.status_code}")
                logger.warning(f"响应内容: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 初始化管理员账户失败: {e}")
            return False
    
    async def login_admin(self) -> bool:
        """管理员登录"""
        logger.info("🔐 管理员登录...")
        
        try:
            login_data = {
                "username": config.ADMIN_USERNAME,
                "password": config.ADMIN_PASSWORD
            }
            
            response = await self.client.post(
                "/api/v1/auth/token",
                data=login_data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.admin_token = token_data["access_token"]
                self.client.access_token = self.admin_token
                logger.success("✅ 管理员登录成功")
                return True
            else:
                logger.warning(f"⚠️ 管理员登录失败: {response.status_code}")
                logger.warning(f"响应内容: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 管理员登录失败: {e}")
            return False
    
    async def login_user(self, username: str, password: str) -> bool:
        """用户登录"""
        logger.info(f"🔐 用户登录: {username}")
        
        try:
            login_data = {
                "username": username,
                "password": password
            }
            
            response = await self.client.post(
                "/api/v1/auth/token",
                data=login_data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.client.access_token = token_data["access_token"]
                logger.success("✅ 用户登录成功")
                return True
            else:
                logger.warning(f"⚠️ 用户登录失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 用户登录失败: {e}")
            return False


class TestDataManager:
    """测试数据管理器"""
    
    def __init__(self, client: TestHTTPClient):
        self.client = client
        self.created_users: List[str] = []
        self.created_tasks: List[str] = []
        self.created_schedules: List[str] = []
    
    async def create_test_user(self, suffix: str = None) -> Optional[Dict[str, Any]]:
        """创建测试用户"""
        user_data = config.get_test_user_data(suffix)
        
        logger.info(f"👤 创建测试用户: {user_data['username']}")
        
        try:
            response = await self.client.post(
                "/api/v1/user/add",
                json=user_data
            )
            
            if response.status_code == 201:
                result = response.json()
                self.created_users.append(result["id"])
                logger.success(f"✅ 用户创建成功: {result['username']}")
                return result
            else:
                logger.warning(f"⚠️ 用户创建失败: {response.status_code}")
                logger.warning(f"响应内容: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 创建用户失败: {e}")
            return None
    
    async def create_test_task(self, task_type: str, suffix: str = None) -> Optional[Dict[str, Any]]:
        """创建测试任务"""
        task_data = config.get_test_task_data(task_type, suffix)
        
        logger.info(f"📋 创建测试任务: {task_data['task_name']}")
        
        try:
            response = await self.client.post(
                "/api/v1/task/",
                json=task_data
            )
            
            if response.status_code == 201:
                result = response.json()
                self.created_tasks.append(result["id"])
                logger.success(f"✅ 任务创建成功: {result['task_name']}")
                return result
            else:
                logger.warning(f"⚠️ 任务创建失败: {response.status_code}")
                logger.warning(f"响应内容: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 创建任务失败: {e}")
            return None
    
    async def create_test_schedule(self, schedule_type: str, task_id: str) -> Optional[Dict[str, Any]]:
        """创建测试调度"""
        schedule_data = config.get_test_schedule_data(schedule_type, task_id)
        
        logger.info(f"⏰ 创建测试调度: {schedule_type}")
        
        try:
            response = await self.client.post(
                "/api/v1/scheduler/schedules",
                json=schedule_data
            )
            
            if response.status_code == 201:
                result = response.json()
                self.created_schedules.append(result["id"])
                logger.success(f"✅ 调度创建成功: {result['id']}")
                return result
            else:
                logger.warning(f"⚠️ 调度创建失败: {response.status_code}")
                logger.warning(f"响应内容: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 创建调度失败: {e}")
            return None
    
    async def cleanup_all(self):
        """清理所有测试数据"""
        if not config.TEST_DATA.get("cleanup_after_test", True):
            logger.info("ℹ️ 跳过测试数据清理")
            return
        
        logger.info("🧹 清理测试数据...")
        
        # 清理调度
        for schedule_id in self.created_schedules:
            try:
                await self.client.delete(f"/api/v1/scheduler/schedules/{schedule_id}")
                logger.info(f"🗑️ 调度已删除: {schedule_id}")
            except Exception as e:
                logger.warning(f"⚠️ 删除调度失败: {e}")
        
        # 清理任务
        for task_id in self.created_tasks:
            try:
                await self.client.delete(f"/api/v1/task/{task_id}")
                logger.info(f"🗑️ 任务已删除: {task_id}")
            except Exception as e:
                logger.warning(f"⚠️ 删除任务失败: {e}")
        
        # 清理用户
        for user_id in self.created_users:
            try:
                await self.client.delete(f"/api/v1/user/{user_id}")
                logger.info(f"🗑️ 用户已删除: {user_id}")
            except Exception as e:
                logger.warning(f"⚠️ 删除用户失败: {e}")
        
        logger.success("✅ 测试数据清理完成")


class TestValidator:
    """测试结果验证器"""
    
    @staticmethod
    def validate_response(response: httpx.Response, expected_status: int = 200) -> bool:
        """验证HTTP响应"""
        if response.status_code != expected_status:
            logger.warning(f"⚠️ 响应状态码不匹配: 期望 {expected_status}, 实际 {response.status_code}")
            return False
        
        try:
            response.json()
            return True
        except json.JSONDecodeError:
            logger.warning("⚠️ 响应不是有效的JSON格式")
            return False
    
    @staticmethod
    def validate_user_data(user_data: Dict[str, Any]) -> bool:
        """验证用户数据"""
        required_fields = ["id", "username", "email", "full_name"]
        
        for field in required_fields:
            if field not in user_data:
                logger.warning(f"⚠️ 用户数据缺少字段: {field}")
                return False
        
        return True
    
    @staticmethod
    def validate_task_data(task_data: Dict[str, Any]) -> bool:
        """验证任务数据"""
        required_fields = ["id", "task_name", "task_type", "status"]
        
        for field in required_fields:
            if field not in task_data:
                logger.warning(f"⚠️ 任务数据缺少字段: {field}")
                return False
        
        return True
    
    @staticmethod
    def validate_execution_data(execution_data: Dict[str, Any]) -> bool:
        """验证执行数据"""
        required_fields = ["id", "task_id", "status"]
        
        for field in required_fields:
            if field not in execution_data:
                logger.warning(f"⚠️ 执行数据缺少字段: {field}")
                return False
        
        return True


class TestHelper:
    """测试辅助工具"""
    
    @staticmethod
    def generate_suffix() -> str:
        """生成测试后缀"""
        return str(int(time.time()))
    
    @staticmethod
    async def wait_for_execution(
        client: TestHTTPClient, 
        execution_id: str, 
        max_wait: int = None,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """等待任务执行完成"""
        max_wait = max_wait or config.TEST_DATA.get("max_execution_time", 120)
        start_time = time.time()
        
        logger.info(f"⏳ 等待任务执行完成 (最多等待 {max_wait} 秒)...")
        
        while time.time() - start_time < max_wait:
            try:
                response = await client.get(f"/api/v1/task/executions/{execution_id}")
                
                if response.status_code == 200:
                    execution_data = response.json()
                    status = execution_data.get("status", "unknown")
                    
                    logger.info(f"📊 执行状态: {status}")
                    
                    if status in ["completed", "failed", "cancelled"]:
                        logger.success(f"✅ 任务执行完成: {status}")
                        return execution_data
                    
                    await asyncio.sleep(poll_interval)
                else:
                    logger.warning(f"⚠️ 获取执行状态失败: {response.status_code}")
                    await asyncio.sleep(poll_interval)
                    
            except Exception as e:
                logger.warning(f"⚠️ 等待执行时出错: {e}")
                await asyncio.sleep(poll_interval)
        
        logger.warning("⚠️ 任务执行超时")
        return {}
    
    @staticmethod
    def setup_logging():
        """设置日志"""
        logger.remove()
        logger.add(
            lambda msg: print(msg, end=""),
            format=config.LOG_CONFIG["format"],
            level=config.LOG_CONFIG["level"]
        )
