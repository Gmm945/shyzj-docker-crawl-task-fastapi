#!/usr/bin/env python3
"""
数据采集任务管理系统 - 测试例子脚本
==========================================

这个脚本包含了系统各个功能的测试例子，包括：
1. 用户注册和认证
2. 任务创建和管理
3. 任务调度
4. 任务执行监控
5. 系统健康检查

使用方法：
    python test_examples.py

或者使用PDM运行：
    pdm run python test_examples.py
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import httpx
from loguru import logger


class DataPlatformTester:
    """数据采集任务管理系统测试类"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.access_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.task_id: Optional[str] = None
        self.schedule_id: Optional[str] = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送HTTP请求的通用方法"""
        url = f"{self.base_url}{endpoint}"
        
        # 添加认证头
        if self.access_token:
            headers = kwargs.get('headers', {})
            headers['Authorization'] = f'Bearer {self.access_token}'
            kwargs['headers'] = headers
        
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP请求失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"响应内容: {e.response.text}")
            raise
    
    async def test_system_health(self) -> bool:
        """测试系统健康状态"""
        logger.info("🔍 测试系统健康状态...")
        
        try:
            # 测试根路径
            result = await self._make_request("GET", "/api/v1/")
            logger.success(f"✅ 系统根路径响应: {result}")
            
            # 测试Redis连接
            redis_result = await self._make_request("GET", "/api/v1/monitoring/redis-health")
            logger.success(f"✅ Redis健康检查: {redis_result}")
            
            return True
        except Exception as e:
            logger.error(f"❌ 系统健康检查失败: {e}")
            return False
    
    async def test_user_management(self) -> bool:
        """测试用户管理功能"""
        logger.info("👤 测试用户管理功能...")
        
        try:
            # 1. 注册新用户
            test_user = {
                "username": f"test_user_{int(time.time())}",
                "email": f"test_{int(time.time())}@example.com",
                "password": "TestPassword123!",
                "full_name": "测试用户"
            }
            
            logger.info(f"📝 注册用户: {test_user['username']}")
            register_result = await self._make_request(
                "POST", 
                "/api/v1/user/add", 
                json=test_user
            )
            logger.success(f"✅ 用户注册成功: {register_result}")
            
            # 2. 用户登录
            login_data = {
                "username": test_user["username"],
                "password": test_user["password"]
            }
            
            logger.info("🔐 用户登录...")
            login_result = await self._make_request(
                "POST",
                "/api/v1/auth/token",
                data=login_data
            )
            
            self.access_token = login_result["access_token"]
            self.user_id = register_result["id"]
            logger.success(f"✅ 登录成功，获得访问令牌")
            
            # 3. 获取用户信息
            logger.info("📋 获取用户信息...")
            user_info = await self._make_request("GET", f"/api/v1/user/{self.user_id}")
            logger.success(f"✅ 用户信息: {user_info}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 用户管理测试失败: {e}")
            return False
    
    async def test_task_management(self) -> bool:
        """测试任务管理功能"""
        logger.info("📋 测试任务管理功能...")
        
        try:
            # 1. 创建Docker爬虫任务
            docker_task = {
                "task_name": f"测试Docker爬虫任务_{int(time.time())}",
                "task_type": "docker-crawl",
                "description": "这是一个测试用的Docker爬虫任务",
                "base_url": "https://httpbin.org",
                "base_url_params": {"test": "true"},
                "need_user_login": False,
                "extract_config": {
                    "selectors": {
                        "title": "h1",
                        "content": ".content"
                    },
                    "pagination": {
                        "enabled": False
                    }
                }
            }
            
            logger.info("🆕 创建Docker爬虫任务...")
            task_result = await self._make_request(
                "POST",
                "/api/v1/task/",
                json=docker_task
            )
            self.task_id = task_result["id"]
            logger.success(f"✅ 任务创建成功: {task_result}")
            
            # 2. 获取任务列表
            logger.info("📝 获取任务列表...")
            tasks_list = await self._make_request("GET", "/api/v1/task/")
            logger.success(f"✅ 任务列表: 共{len(tasks_list['items'])}个任务")
            
            # 3. 更新任务状态
            logger.info("🔄 更新任务状态...")
            update_result = await self._make_request(
                "PUT",
                f"/api/v1/task/{self.task_id}/status",
                json={"status": "active"}
            )
            logger.success(f"✅ 任务状态更新成功: {update_result}")
            
            # 4. 创建API调用任务
            api_task = {
                "task_name": f"测试API任务_{int(time.time())}",
                "task_type": "api",
                "description": "这是一个测试用的API调用任务",
                "base_url": "https://jsonplaceholder.typicode.com/posts/1",
                "base_url_params": {},
                "need_user_login": False,
                "extract_config": {
                    "method": "GET",
                    "headers": {
                        "Content-Type": "application/json"
                    }
                }
            }
            
            logger.info("🆕 创建API任务...")
            api_task_result = await self._make_request(
                "POST",
                "/api/v1/task/",
                json=api_task
            )
            logger.success(f"✅ API任务创建成功: {api_task_result}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 任务管理测试失败: {e}")
            return False
    
    async def test_task_scheduling(self) -> bool:
        """测试任务调度功能"""
        logger.info("⏰ 测试任务调度功能...")
        
        try:
            if not self.task_id:
                logger.error("❌ 没有可用的任务ID")
                return False
            
            # 1. 创建立即执行调度
            immediate_schedule = {
                "task_id": self.task_id,
                "schedule_type": "immediate",
                "schedule_config": {},
                "is_active": True
            }
            
            logger.info("⏰ 创建立即执行调度...")
            schedule_result = await self._make_request(
                "POST",
                "/api/v1/scheduler/schedules",
                json=immediate_schedule
            )
            self.schedule_id = schedule_result["id"]
            logger.success(f"✅ 立即执行调度创建成功: {schedule_result}")
            
            # 2. 创建定时调度（每分钟执行一次）
            cron_schedule = {
                "task_id": self.task_id,
                "schedule_type": "scheduled",
                "schedule_config": {
                    "cron_expression": "*/1 * * * *",
                    "timezone": "Asia/Shanghai"
                },
                "is_active": True
            }
            
            logger.info("⏰ 创建定时调度...")
            cron_result = await self._make_request(
                "POST",
                "/api/v1/scheduler/schedules",
                json=cron_schedule
            )
            logger.success(f"✅ 定时调度创建成功: {cron_result}")
            
            # 3. 获取调度列表
            logger.info("📋 获取调度列表...")
            schedules_list = await self._make_request("GET", "/api/v1/scheduler/schedules")
            logger.success(f"✅ 调度列表: 共{len(schedules_list['items'])}个调度")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 任务调度测试失败: {e}")
            return False
    
    async def test_task_execution(self) -> bool:
        """测试任务执行功能"""
        logger.info("🚀 测试任务执行功能...")
        
        try:
            if not self.task_id:
                logger.error("❌ 没有可用的任务ID")
                return False
            
            # 1. 手动执行任务
            logger.info("🚀 手动执行任务...")
            execution_data = {
                "execution_name": f"手动执行测试_{int(time.time())}",
                "task_id": self.task_id
            }
            
            execution_result = await self._make_request(
                "POST",
                "/api/v1/task/execute",
                json=execution_data
            )
            logger.success(f"✅ 任务执行请求成功: {execution_result}")
            
            execution_id = execution_result["execution_id"]
            
            # 2. 等待一段时间后检查执行状态
            logger.info("⏳ 等待任务执行...")
            await asyncio.sleep(5)
            
            # 3. 获取执行状态
            logger.info("📊 检查执行状态...")
            status_result = await self._make_request(
                "GET",
                f"/api/v1/task/executions/{execution_id}"
            )
            logger.success(f"✅ 执行状态: {status_result}")
            
            # 4. 获取执行日志
            logger.info("📝 获取执行日志...")
            logs_result = await self._make_request(
                "GET",
                f"/api/v1/task/executions/{execution_id}/logs"
            )
            logger.success(f"✅ 执行日志: {logs_result}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 任务执行测试失败: {e}")
            return False
    
    async def test_monitoring(self) -> bool:
        """测试监控功能"""
        logger.info("📊 测试监控功能...")
        
        try:
            # 1. 获取系统状态
            logger.info("📊 获取系统状态...")
            system_status = await self._make_request("GET", "/api/v1/monitoring/status")
            logger.success(f"✅ 系统状态: {system_status}")
            
            # 2. 获取任务统计
            logger.info("📈 获取任务统计...")
            task_stats = await self._make_request("GET", "/api/v1/monitoring/task-stats")
            logger.success(f"✅ 任务统计: {task_stats}")
            
            # 3. 获取执行统计
            logger.info("📈 获取执行统计...")
            execution_stats = await self._make_request("GET", "/api/v1/monitoring/execution-stats")
            logger.success(f"✅ 执行统计: {execution_stats}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 监控功能测试失败: {e}")
            return False
    
    async def test_cleanup(self) -> bool:
        """测试清理功能"""
        logger.info("🧹 测试清理功能...")
        
        try:
            # 1. 删除调度
            if self.schedule_id:
                logger.info("🗑️ 删除测试调度...")
                await self._make_request(
                    "DELETE",
                    f"/api/v1/scheduler/schedules/{self.schedule_id}"
                )
                logger.success("✅ 调度删除成功")
            
            # 2. 删除任务
            if self.task_id:
                logger.info("🗑️ 删除测试任务...")
                await self._make_request(
                    "DELETE",
                    f"/api/v1/task/{self.task_id}"
                )
                logger.success("✅ 任务删除成功")
            
            # 3. 删除用户
            if self.user_id:
                logger.info("🗑️ 删除测试用户...")
                await self._make_request(
                    "DELETE",
                    f"/api/v1/user/{self.user_id}"
                )
                logger.success("✅ 用户删除成功")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 清理功能测试失败: {e}")
            return False
    
    async def run_all_tests(self) -> bool:
        """运行所有测试"""
        logger.info("🚀 开始运行数据采集任务管理系统测试...")
        
        test_results = []
        
        # 1. 系统健康检查
        test_results.append(await self.test_system_health())
        
        # 2. 用户管理测试
        test_results.append(await self.test_user_management())
        
        # 3. 任务管理测试
        test_results.append(await self.test_task_management())
        
        # 4. 任务调度测试
        test_results.append(await self.test_task_scheduling())
        
        # 5. 任务执行测试
        test_results.append(await self.test_task_execution())
        
        # 6. 监控功能测试
        test_results.append(await self.test_monitoring())
        
        # 7. 清理测试
        test_results.append(await self.test_cleanup())
        
        # 统计结果
        passed_tests = sum(test_results)
        total_tests = len(test_results)
        
        logger.info(f"📊 测试结果: {passed_tests}/{total_tests} 通过")
        
        if passed_tests == total_tests:
            logger.success("🎉 所有测试通过！系统运行正常！")
            return True
        else:
            logger.warning(f"⚠️ {total_tests - passed_tests} 个测试失败")
            return False


async def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    
    logger.info("=" * 60)
    logger.info("🔧 数据采集任务管理系统 - 测试脚本")
    logger.info("=" * 60)
    
    async with DataPlatformTester() as tester:
        success = await tester.run_all_tests()
        
        logger.info("=" * 60)
        if success:
            logger.success("🎉 测试完成！系统运行正常！")
        else:
            logger.error("❌ 测试完成！部分功能存在问题！")
        logger.info("=" * 60)
        
        return success


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())
