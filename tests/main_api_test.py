#!/usr/bin/env python3
"""
主要接口测试脚本
===============

测试系统中的核心API接口，包括：
1. 认证接口 (Authentication)
2. 用户管理接口 (User Management) 
3. 任务管理接口 (Task Management)
4. 监控接口 (Monitoring)
5. 调度器接口 (Scheduler)

使用方法：
    python tests/main_api_test.py
    python tests/run_tests.py --main
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from uuid import uuid4

import httpx
from loguru import logger

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_config import config
from tests.test_utils import TestHTTPClient, AuthManager, TestDataManager


class MainAPITester:
    """主要接口测试类"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.BASE_URL
        self.client = TestHTTPClient(self.base_url)
        self.auth_manager = AuthManager(self.client)
        self.data_manager = TestDataManager(self.client)
        
        # 测试数据存储
        self.test_data = {
            "admin_token": None,
            "test_user_token": None,
            "test_user_id": None,
            "test_task_id": None,
            "test_execution_id": None,
        }
        
        # 测试结果统计
        self.test_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0
        }
    
    def log_test_result(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        self.test_results["total"] += 1
        if success:
            self.test_results["passed"] += 1
            logger.success(f"✅ {test_name}: {message}")
        else:
            self.test_results["failed"] += 1
            logger.error(f"❌ {test_name}: {message}")
    
    async def test_system_health(self) -> bool:
        """测试系统健康状态"""
        try:
            response = await self.client.get("/api/v1/")
            if response.status_code == 200:
                data = response.json()
                self.log_test_result("系统健康检查", True, f"系统正常运行: {data.get('message', '')}")
                return True
            else:
                self.log_test_result("系统健康检查", False, f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test_result("系统健康检查", False, str(e))
            return False
    
    async def test_auth_apis(self) -> bool:
        """测试认证相关接口"""
        logger.info("🔐 测试认证接口...")
        
        # 1. 初始化管理员账户
        try:
            response = await self.client.post("/api/v1/user/init-admin")
            if response.status_code in [200, 400]:  # 200=创建成功, 400=已存在
                self.log_test_result("初始化管理员", True, "管理员账户已就绪")
            else:
                self.log_test_result("初始化管理员", False, f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test_result("初始化管理员", False, str(e))
            return False
        
        # 2. 管理员登录
        try:
            success = await self.auth_manager.login_admin()
            if success:
                self.test_data["admin_token"] = self.auth_manager.admin_token
                self.log_test_result("管理员登录", True, "登录成功")
            else:
                self.log_test_result("管理员登录", False, "登录失败")
                return False
        except Exception as e:
            self.log_test_result("管理员登录", False, str(e))
            return False
        
        # 3. 获取当前用户信息
        try:
            response = await self.client.get("/api/v1/auth/me")
            if response.status_code == 200:
                user_data = response.json()
                self.log_test_result("获取用户信息", True, f"用户: {user_data.get('data', {}).get('username', '')}")
            else:
                self.log_test_result("获取用户信息", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("获取用户信息", False, str(e))
        
        return True
    
    async def test_user_apis(self) -> bool:
        """测试用户管理接口"""
        logger.info("👥 测试用户管理接口...")
        
        # 1. 创建测试用户
        try:
            user_data = config.get_test_user_data()
            response = await self.client.post("/api/v1/user/add", json=user_data)
            if response.status_code == 200:
                user_info = response.json()
                self.test_data["test_user_id"] = user_info.get("data", {}).get("user_id")
                self.log_test_result("创建用户", True, f"用户ID: {self.test_data['test_user_id']}")
            else:
                self.log_test_result("创建用户", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test_result("创建用户", False, str(e))
            return False
        
        # 2. 获取用户列表
        try:
            response = await self.client.get("/api/v1/user/list")
            if response.status_code == 200:
                users_data = response.json()
                user_count = len(users_data.get("data", []))
                self.log_test_result("获取用户列表", True, f"共 {user_count} 个用户")
            else:
                self.log_test_result("获取用户列表", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("获取用户列表", False, str(e))
        
        # 3. 获取用户详情
        if self.test_data["test_user_id"]:
            try:
                response = await self.client.get(f"/api/v1/user/{self.test_data['test_user_id']}")
                if response.status_code == 200:
                    user_info = response.json()
                    self.log_test_result("获取用户详情", True, f"用户: {user_info.get('data', {}).get('username', '')}")
                else:
                    self.log_test_result("获取用户详情", False, f"HTTP {response.status_code}")
            except Exception as e:
                self.log_test_result("获取用户详情", False, str(e))
        
        return True
    
    async def test_task_apis(self) -> bool:
        """测试任务管理接口"""
        logger.info("📋 测试任务管理接口...")
        
        # 1. 创建测试任务
        try:
            task_data = config.get_test_task_data("api_task")
            response = await self.client.post("/api/v1/task/add", json=task_data)
            if response.status_code == 200:
                task_info = response.json()
                self.test_data["test_task_id"] = task_info.get("data", {}).get("task_id")
                self.log_test_result("创建任务", True, f"任务ID: {self.test_data['test_task_id']}")
            else:
                self.log_test_result("创建任务", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test_result("创建任务", False, str(e))
            return False
        
        # 2. 获取任务列表
        try:
            response = await self.client.get("/api/v1/task/list")
            if response.status_code == 200:
                tasks_data = response.json()
                task_items = tasks_data.get("data", {}).get("items", [])
                task_count = len(task_items)
                self.log_test_result("获取任务列表", True, f"共 {task_count} 个任务")
            else:
                self.log_test_result("获取任务列表", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("获取任务列表", False, str(e))
        
        # 3. 获取任务详情
        if self.test_data["test_task_id"]:
            try:
                response = await self.client.get(f"/api/v1/task/{self.test_data['test_task_id']}")
                if response.status_code == 200:
                    task_info = response.json()
                    self.log_test_result("获取任务详情", True, f"任务: {task_info.get('data', {}).get('task_name', '')}")
                else:
                    self.log_test_result("获取任务详情", False, f"HTTP {response.status_code}")
            except Exception as e:
                self.log_test_result("获取任务详情", False, str(e))
        
        # 4. 执行任务
        if self.test_data["test_task_id"]:
            try:
                execution_data = {
                    "execution_name": f"测试执行_{int(time.time())}",
                    "config_data": {}
                }
                response = await self.client.post(f"/api/v1/task/{self.test_data['test_task_id']}/execute", json=execution_data)
                if response.status_code == 200:
                    execution_info = response.json()
                    self.test_data["test_execution_id"] = execution_info.get("data", {}).get("execution_id")
                    self.log_test_result("执行任务", True, f"执行ID: {self.test_data['test_execution_id']}")
                else:
                    self.log_test_result("执行任务", False, f"HTTP {response.status_code}: {response.text}")
            except Exception as e:
                self.log_test_result("执行任务", False, str(e))
        
        return True
    
    async def test_monitoring_apis(self) -> bool:
        """测试监控接口"""
        logger.info("📊 测试监控接口...")
        
        # 1. 获取活跃执行任务
        try:
            response = await self.client.get("/api/v1/monitoring/executions/active")
            if response.status_code == 200:
                executions_data = response.json()
                active_count = len(executions_data.get("data", []))
                self.log_test_result("获取活跃执行", True, f"活跃任务: {active_count} 个")
            else:
                self.log_test_result("获取活跃执行", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("获取活跃执行", False, str(e))
        
        # 2. 获取监控统计
        try:
            response = await self.client.get("/api/v1/monitoring/statistics")
            if response.status_code == 200:
                stats_data = response.json()
                stats = stats_data.get("data", {})
                self.log_test_result("获取监控统计", True, f"总执行: {stats.get('total_executions', 0)}")
            else:
                self.log_test_result("获取监控统计", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("获取监控统计", False, str(e))
        
        # 3. 获取执行状态（如果有执行ID）
        if self.test_data["test_execution_id"]:
            try:
                response = await self.client.get(f"/api/v1/monitoring/execution/{self.test_data['test_execution_id']}/status")
                if response.status_code == 200:
                    status_data = response.json()
                    status = status_data.get("data", {}).get("status", "unknown")
                    self.log_test_result("获取执行状态", True, f"状态: {status}")
                else:
                    self.log_test_result("获取执行状态", False, f"HTTP {response.status_code}")
            except Exception as e:
                self.log_test_result("获取执行状态", False, str(e))
        
        return True
    
    async def test_scheduler_apis(self) -> bool:
        """测试调度器接口"""
        logger.info("⏰ 测试调度器接口...")
        
        if not self.test_data["test_task_id"]:
            self.log_test_result("调度器测试", False, "缺少任务ID，跳过调度器测试")
            return False
        
        # 1. 创建调度
        try:
            schedule_data = config.get_test_schedule_data("immediate", self.test_data["test_task_id"])
            response = await self.client.post("/api/v1/scheduler/", json=schedule_data)
            if response.status_code == 200:
                schedule_info = response.json()
                schedule_id = schedule_info.get("data", {}).get("schedule_id")
                self.log_test_result("创建调度", True, f"调度ID: {schedule_id}")
            else:
                self.log_test_result("创建调度", False, f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            self.log_test_result("创建调度", False, str(e))
        
        # 2. 获取任务调度
        try:
            response = await self.client.get(f"/api/v1/scheduler/task/{self.test_data['test_task_id']}")
            if response.status_code == 200:
                schedules_data = response.json()
                schedule_count = len(schedules_data.get("data", []))
                self.log_test_result("获取任务调度", True, f"调度数量: {schedule_count}")
            else:
                self.log_test_result("获取任务调度", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("获取任务调度", False, str(e))
        
        return True
    
    async def cleanup_test_data(self):
        """清理测试数据"""
        logger.info("🧹 清理测试数据...")
        
        # 清理测试任务
        if self.test_data["test_task_id"]:
            try:
                await self.client.delete(f"/api/v1/task/{self.test_data['test_task_id']}")
                logger.info("✅ 测试任务已清理")
            except Exception as e:
                logger.warning(f"⚠️ 清理测试任务失败: {e}")
        
        # 清理测试用户
        if self.test_data["test_user_id"]:
            try:
                await self.client.delete(f"/api/v1/user/{self.test_data['test_user_id']}")
                logger.info("✅ 测试用户已清理")
            except Exception as e:
                logger.warning(f"⚠️ 清理测试用户失败: {e}")
    
    def print_test_summary(self):
        """打印测试总结"""
        logger.info("=" * 50)
        logger.info("📊 测试结果总结")
        logger.info("=" * 50)
        logger.info(f"总测试数: {self.test_results['total']}")
        logger.info(f"✅ 通过: {self.test_results['passed']}")
        logger.info(f"❌ 失败: {self.test_results['failed']}")
        logger.info(f"⏭️ 跳过: {self.test_results['skipped']}")
        
        success_rate = (self.test_results['passed'] / self.test_results['total'] * 100) if self.test_results['total'] > 0 else 0
        logger.info(f"📈 成功率: {success_rate:.1f}%")
        
        if self.test_results['failed'] == 0:
            logger.success("🎉 所有测试通过！")
        else:
            logger.warning(f"⚠️ 有 {self.test_results['failed']} 个测试失败")
    
    async def run_all_tests(self, cleanup: bool = True):
        """运行所有测试"""
        logger.info("🚀 开始主要接口测试...")
        logger.info(f"🌐 测试服务器: {self.base_url}")
        
        try:
            # 1. 系统健康检查
            await self.test_system_health()
            
            # 2. 认证接口测试
            await self.test_auth_apis()
            
            # 3. 用户管理接口测试
            await self.test_user_apis()
            
            # 4. 任务管理接口测试
            await self.test_task_apis()
            
            # 5. 监控接口测试
            await self.test_monitoring_apis()
            
            # 6. 调度器接口测试
            await self.test_scheduler_apis()
            
        except Exception as e:
            logger.error(f"测试过程中发生异常: {e}")
        
        finally:
            # 清理测试数据
            if cleanup and config.TEST_DATA.get("cleanup_after_test", True):
                await self.cleanup_test_data()
            
            # 打印测试总结
            self.print_test_summary()
        
        return self.test_results['failed'] == 0


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="主要接口测试脚本")
    parser.add_argument("--base-url", default=config.BASE_URL, help="测试服务器地址")
    parser.add_argument("--no-cleanup", action="store_true", help="不清理测试数据")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 配置日志
    if args.verbose:
        logger.remove()
        logger.add(sys.stdout, level="DEBUG")
    
    # 创建测试器并运行测试
    tester = MainAPITester(args.base_url)
    success = await tester.run_all_tests(cleanup=not args.no_cleanup)
    
    # 退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
