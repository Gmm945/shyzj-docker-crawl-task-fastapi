#!/usr/bin/env python3
"""
全面的API接口测试脚本
=====================

这个脚本测试系统中的所有API接口，包括：
1. 通用接口 (Common APIs)
2. 用户管理接口 (User Management APIs)
3. 认证接口 (Authentication APIs)
4. 任务管理接口 (Task Management APIs)
5. 调度器接口 (Scheduler APIs)
6. 监控接口 (Monitoring APIs)

使用方法：
    python tests/comprehensive_api_test.py
    python tests/run_tests.py --comprehensive
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
from tests.test_utils import TestHTTPClient, AuthManager, TestDataManager, TestValidator


class ComprehensiveAPITester:
    """全面的API接口测试类"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.BASE_URL
        self.client = TestHTTPClient(self.base_url)
        self.auth_manager = AuthManager(self.client)
        self.data_manager = TestDataManager(self.client)
        self.validator = TestValidator()
        
        # 测试数据存储
        self.test_data = {
            "admin_token": None,
            "test_users": [],
            "test_tasks": [],
            "test_schedules": [],
            "test_executions": []
        }
        
        # 测试结果存储
        self.test_results = {}
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def run_test(self, test_name: str, test_func) -> bool:
        """运行单个测试并记录结果"""
        logger.info(f"🧪 开始测试: {test_name}")
        start_time = time.time()
        
        try:
            result = await test_func()
            duration = time.time() - start_time
            
            self.test_results[test_name] = {
                "success": result,
                "duration": duration,
                "error": None
            }
            
            if result:
                logger.success(f"✅ {test_name} 测试通过 (耗时: {duration:.2f}秒)")
            else:
                logger.error(f"❌ {test_name} 测试失败 (耗时: {duration:.2f}秒)")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.test_results[test_name] = {
                "success": False,
                "duration": duration,
                "error": str(e)
            }
            logger.error(f"❌ {test_name} 测试异常: {e}")
            return False
    
    # ==================== 通用接口测试 ====================
    
    async def test_common_apis(self) -> bool:
        """测试通用接口"""
        logger.info("🌐 测试通用接口...")
        
        try:
            # 1. 系统根路径
            response = await self.client.get("/api/v1/")
            if not self.validator.validate_response(response):
                return False
            
            root_data = response.json()
            logger.success(f"✅ 系统根路径: {root_data}")
            
            # 2. 健康检查
            response = await self.client.get("/api/v1/common/health")
            if not self.validator.validate_response(response):
                return False
            
            health_data = response.json()
            logger.success(f"✅ 健康检查: {health_data}")
            
            # 3. 存活检查
            response = await self.client.get("/api/v1/common/health/liveness")
            if not self.validator.validate_response(response):
                return False
            
            liveness_data = response.json()
            logger.success(f"✅ 存活检查: {liveness_data}")
            
            # 4. 就绪检查
            response = await self.client.get("/api/v1/common/health/readiness")
            if not self.validator.validate_response(response):
                return False
            
            readiness_data = response.json()
            logger.success(f"✅ 就绪检查: {readiness_data}")
            
            # 5. 系统统计
            response = await self.client.get("/api/v1/common/stats")
            if not self.validator.validate_response(response):
                return False
            
            stats_data = response.json()
            logger.success(f"✅ 系统统计: {stats_data}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 通用接口测试失败: {e}")
            return False
    
    # ==================== 用户管理接口测试 ====================
    
    async def test_user_management_apis(self) -> bool:
        """测试用户管理接口"""
        logger.info("👤 测试用户管理接口...")
        
        try:
            # 1. 初始化管理员账户
            response = await self.client.post("/api/v1/user/init-admin")
            if response.status_code not in [200, 400]:  # 200=成功创建, 400=已存在
                logger.warning(f"⚠️ 管理员初始化: {response.status_code}")
            
            # 2. 管理员登录
            login_data = {
                "username": config.ADMIN_USERNAME,
                "password": config.ADMIN_PASSWORD
            }
            
            response = await self.client.post("/api/v1/auth/token", data=login_data)
            if not self.validator.validate_response(response):
                return False
            
            token_data = response.json()
            self.test_data["admin_token"] = token_data["access_token"]
            self.client.access_token = token_data["access_token"]
            logger.success("✅ 管理员登录成功")
            
            # 3. 创建测试用户
            test_user_data = config.get_test_user_data()
            response = await self.client.post("/api/v1/user/add", json=test_user_data)
            if not self.validator.validate_response(response, 200):  # 用户创建返回200
                return False
            
            user_data = response.json()
            # 用户创建接口只返回user_id，需要构造完整的用户数据
            full_user_data = {
                "id": user_data["data"]["user_id"],
                "username": test_user_data["username"],
                "email": test_user_data["email"],
                "full_name": test_user_data["full_name"]
            }
            self.test_data["test_users"].append(full_user_data)
            logger.success(f"✅ 用户创建成功: {test_user_data['username']}")
            
            # 4. 获取用户列表
            response = await self.client.get("/api/v1/user/list")
            if not self.validator.validate_response(response):
                return False
            
            users_list = response.json()
            logger.success(f"✅ 用户列表: 共{len(users_list['data']['items'])}个用户")
            
            # 5. 获取用户详情
            user_id = user_data['data']['user_id']
            response = await self.client.get(f"/api/v1/user/{user_id}")
            if not self.validator.validate_response(response):
                return False
            
            user_detail = response.json()
            logger.success(f"✅ 用户详情: {user_detail['data']['username']}")
            
            # 6. 更新用户信息
            update_data = {
                "full_name": "更新后的测试用户",
                "email": f"updated_{test_user_data['email']}"
            }
            
            response = await self.client.put(f"/api/v1/user/{user_id}", json=update_data)
            if not self.validator.validate_response(response):
                return False
            
            updated_user = response.json()
            logger.success(f"✅ 用户更新成功: {updated_user['data']['full_name']}")
            
            # 7. 切换用户状态
            response = await self.client.post(f"/api/v1/user/{user_id}/toggle-active")
            if not self.validator.validate_response(response):
                return False
            
            toggle_result = response.json()
            logger.success(f"✅ 用户状态切换: {toggle_result}")
            
            # 8. 获取活跃用户统计
            response = await self.client.get("/api/v1/user/stats/active-count")
            if not self.validator.validate_response(response):
                return False
            
            stats = response.json()
            logger.success(f"✅ 活跃用户统计: {stats}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 用户管理接口测试失败: {e}")
            return False
    
    # ==================== 认证接口测试 ====================
    
    async def test_authentication_apis(self) -> bool:
        """测试认证接口"""
        logger.info("🔐 测试认证接口...")
        
        try:
            if not self.test_data["test_users"]:
                logger.warning("⚠️ 没有测试用户，跳过认证接口测试")
                return True
            
            test_user = self.test_data["test_users"][0]
            
            # 1. 用户登录
            login_data = {
                "username": test_user["username"],
                "password": config.TEST_USER_PASSWORD
            }
            
            response = await self.client.post("/api/v1/auth/token", data=login_data)
            if not self.validator.validate_response(response):
                return False
            
            user_token_data = response.json()
            logger.success("✅ 用户登录成功")
            
            # 2. 获取当前用户信息
            original_token = self.client.access_token
            self.client.access_token = user_token_data["access_token"]
            
            response = await self.client.get("/api/v1/auth/me")
            if not self.validator.validate_response(response):
                self.client.access_token = original_token
                return False
            
            me_data = response.json()
            # 检查响应格式，可能是嵌套在data字段中
            if 'data' in me_data:
                username = me_data['data'].get('username', 'Unknown')
            else:
                username = me_data.get('username', 'Unknown')
            logger.success(f"✅ 当前用户信息: {username}")
            
            # 3. 修改密码
            change_password_data = {
                "old_password": config.TEST_USER_PASSWORD,
                "new_password": "NewPassword123!",
                "confirm_password": "NewPassword123!"
            }
            
            response = await self.client.post("/api/v1/auth/change-password", json=change_password_data)
            if not self.validator.validate_response(response):
                self.client.access_token = original_token
                return False
            
            change_result = response.json()
            logger.success(f"✅ 密码修改成功: {change_result}")
            
            # 4. 使用新密码登录
            new_login_data = {
                "username": test_user["username"],
                "password": "NewPassword123!"
            }
            
            response = await self.client.post("/api/v1/auth/token", data=new_login_data)
            if not self.validator.validate_response(response):
                self.client.access_token = original_token
                return False
            
            new_token_data = response.json()
            logger.success("✅ 新密码登录成功")
            
            # 5. 登出
            response = await self.client.post("/api/v1/auth/logout")
            if response.status_code in [200, 204]:
                logger.success("✅ 用户登出成功")
            else:
                logger.warning(f"⚠️ 登出响应: {response.status_code}")
            
            # 恢复管理员token
            self.client.access_token = original_token
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 认证接口测试失败: {e}")
            return False
    
    # ==================== 任务管理接口测试 ====================
    
    async def test_task_management_apis(self) -> bool:
        """测试任务管理接口"""
        logger.info("📋 测试任务管理接口...")
        
        try:
            # 1. 创建API任务
            api_task_data = config.get_test_task_data("api_task")
            response = await self.client.post("/api/v1/task/add", json=api_task_data)
            if not self.validator.validate_response(response, 200):
                return False
            
            api_task = response.json()
            self.test_data["test_tasks"].append(api_task)
            logger.success(f"✅ API任务创建成功: {api_task['data']['task_id']}")
            
            # 2. 创建Docker爬虫任务
            docker_task_data = config.get_test_task_data("docker_crawl_task")
            response = await self.client.post("/api/v1/task/add", json=docker_task_data)
            if not self.validator.validate_response(response, 200):
                return False
            
            docker_task = response.json()
            self.test_data["test_tasks"].append(docker_task)
            logger.success(f"✅ Docker任务创建成功: {docker_task['data']['task_id']}")
            
            # 3. 获取任务列表
            response = await self.client.get("/api/v1/task/list")
            if not self.validator.validate_response(response):
                return False
            
            tasks_list = response.json()
            logger.success(f"✅ 任务列表: 共{len(tasks_list['data']['items'])}个任务")
            
            # 4. 获取任务详情
            task_id = api_task['data']['task_id']
            response = await self.client.get(f"/api/v1/task/{task_id}")
            if not self.validator.validate_response(response):
                return False
            
            task_detail = response.json()
            logger.success(f"✅ 任务详情: {task_detail['data']['task_name']}")
            
            # 5. 更新任务
            update_task_data = {
                "description": "更新后的任务描述",
                "extract_config": {
                    "method": "GET",
                    "timeout": 60
                }
            }
            
            response = await self.client.put(f"/api/v1/task/{api_task['id']}", json=update_task_data)
            if not self.validator.validate_response(response):
                return False
            
            updated_task = response.json()
            logger.success(f"✅ 任务更新成功: {updated_task['description']}")
            
            # 6. 执行任务
            execution_data = {
                "execution_name": f"测试执行_{int(time.time())}",
                "task_id": api_task["id"]
            }
            
            response = await self.client.post(f"/api/v1/task/{api_task['id']}/execute", json=execution_data)
            if not self.validator.validate_response(response, 202):
                return False
            
            execution_result = response.json()
            self.test_data["test_executions"].append(execution_result)
            logger.success(f"✅ 任务执行请求成功: {execution_result['execution_id']}")
            
            # 7. 获取任务执行列表
            response = await self.client.get(f"/api/v1/task/executions/{api_task['id']}")
            if not self.validator.validate_response(response):
                return False
            
            executions_list = response.json()
            logger.success(f"✅ 执行列表: 共{len(executions_list['items'])}个执行")
            
            # 8. 停止任务执行
            if self.test_data["test_executions"]:
                execution_id = self.test_data["test_executions"][0]["execution_id"]
                response = await self.client.post(f"/api/v1/task/{api_task['id']}/stop")
                if response.status_code in [200, 202]:
                    logger.success("✅ 任务停止请求成功")
                else:
                    logger.warning(f"⚠️ 任务停止响应: {response.status_code}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 任务管理接口测试失败: {e}")
            return False
    
    # ==================== 调度器接口测试 ====================
    
    async def test_scheduler_apis(self) -> bool:
        """测试调度器接口"""
        logger.info("⏰ 测试调度器接口...")
        
        try:
            if not self.test_data["test_tasks"]:
                logger.warning("⚠️ 没有测试任务，跳过调度器接口测试")
                return True
            
            task = self.test_data["test_tasks"][0]
            
            # 1. 创建立即执行调度
            immediate_schedule_data = config.get_test_schedule_data("immediate", task["id"])
            response = await self.client.post("/api/v1/scheduler/schedules", json=immediate_schedule_data)
            if not self.validator.validate_response(response, 200):
                return False
            
            immediate_schedule = response.json()
            self.test_data["test_schedules"].append(immediate_schedule)
            logger.success(f"✅ 立即调度创建成功: {immediate_schedule['id']}")
            
            # 2. 创建定时调度
            cron_schedule_data = config.get_test_schedule_data("cron", task["id"])
            response = await self.client.post("/api/v1/scheduler/schedules", json=cron_schedule_data)
            if not self.validator.validate_response(response, 200):
                return False
            
            cron_schedule = response.json()
            self.test_data["test_schedules"].append(cron_schedule)
            logger.success(f"✅ 定时调度创建成功: {cron_schedule['id']}")
            
            # 3. 获取任务调度列表
            response = await self.client.get(f"/api/v1/scheduler/schedules/task/{task['id']}")
            if not self.validator.validate_response(response):
                return False
            
            schedules_list = response.json()
            logger.success(f"✅ 任务调度列表: 共{len(schedules_list['items'])}个调度")
            
            # 4. 切换调度状态
            response = await self.client.put(f"/api/v1/scheduler/schedules/{immediate_schedule['id']}/toggle")
            if not self.validator.validate_response(response):
                return False
            
            toggle_result = response.json()
            logger.success(f"✅ 调度状态切换: {toggle_result}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 调度器接口测试失败: {e}")
            return False
    
    # ==================== 监控接口测试 ====================
    
    async def test_monitoring_apis(self) -> bool:
        """测试监控接口"""
        logger.info("📊 测试监控接口...")
        
        try:
            # 1. 发送心跳
            heartbeat_data = {
                "execution_id": 1,  # 使用整数ID
                "container_id": f"test_container_{int(time.time())}",
                "status": "running",
                "progress": {"current": 50, "total": 100}
            }
            
            response = await self.client.post("/api/v1/monitoring/heartbeat", json=heartbeat_data)
            if response.status_code in [200, 201]:
                logger.success("✅ 心跳发送成功")
            else:
                logger.warning(f"⚠️ 心跳响应: {response.status_code}")
            
            # 2. 发送完成通知（跳过，因为没有执行记录）
            logger.info("⚠️ 跳过完成通知测试 - 没有执行记录")
            
            # 3. 获取执行状态
            if self.test_data["test_executions"]:
                execution_id = self.test_data["test_executions"][0]["execution_id"]
                response = await self.client.get(f"/api/v1/monitoring/execution/{execution_id}/status")
                if response.status_code in [200, 404]:  # 404可能是因为执行已完成
                    if response.status_code == 200:
                        status_data = response.json()
                        logger.success(f"✅ 执行状态: {status_data}")
                    else:
                        logger.info("ℹ️ 执行状态: 执行不存在或已完成")
                else:
                    logger.warning(f"⚠️ 执行状态响应: {response.status_code}")
            
            # 4. 获取活跃执行列表
            response = await self.client.get("/api/v1/monitoring/executions/active")
            if not self.validator.validate_response(response):
                return False
            
            active_executions = response.json()
            if 'data' in active_executions:
                executions_count = len(active_executions['data'])
                logger.success(f"✅ 活跃执行列表: 共{executions_count}个执行")
            else:
                logger.success(f"✅ 活跃执行列表: {active_executions}")
            
            # 5. 获取系统统计
            response = await self.client.get("/api/v1/monitoring/statistics")
            if not self.validator.validate_response(response):
                return False
            
            statistics = response.json()
            logger.success(f"✅ 系统统计: {statistics}")
            
            # 6. 检查超时
            response = await self.client.post("/api/v1/monitoring/check-timeouts")
            if response.status_code in [200, 202]:
                timeout_result = response.json()
                logger.success(f"✅ 超时检查: {timeout_result}")
            else:
                logger.warning(f"⚠️ 超时检查响应: {response.status_code}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 监控接口测试失败: {e}")
            return False
    
    # ==================== 数据清理 ====================
    
    async def cleanup_test_data(self) -> bool:
        """清理测试数据"""
        logger.info("🧹 清理测试数据...")
        
        try:
            # 清理调度
            for schedule in self.test_data["test_schedules"]:
                try:
                    response = await self.client.delete(f"/api/v1/scheduler/schedules/{schedule['id']}")
                    if response.status_code in [200, 204]:
                        logger.info(f"🗑️ 调度已删除: {schedule['id']}")
                except Exception as e:
                    logger.warning(f"⚠️ 删除调度失败: {e}")
            
            # 清理任务
            for task in self.test_data["test_tasks"]:
                try:
                    response = await self.client.delete(f"/api/v1/task/{task['id']}")
                    if response.status_code in [200, 204]:
                        logger.info(f"🗑️ 任务已删除: {task['id']}")
                except Exception as e:
                    logger.warning(f"⚠️ 删除任务失败: {e}")
            
            # 清理用户
            for user in self.test_data["test_users"]:
                try:
                    response = await self.client.delete(f"/api/v1/user/{user['id']}")
                    if response.status_code in [200, 204]:
                        logger.info(f"🗑️ 用户已删除: {user['id']}")
                except Exception as e:
                    logger.warning(f"⚠️ 删除用户失败: {e}")
            
            logger.success("✅ 测试数据清理完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 测试数据清理失败: {e}")
            return False
    
    # ==================== 主测试流程 ====================
    
    async def run_all_tests(self) -> bool:
        """运行所有API接口测试"""
        logger.info("🚀 开始全面的API接口测试...")
        
        test_suites = [
            ("通用接口测试", self.test_common_apis),
            ("用户管理接口测试", self.test_user_management_apis),
            ("认证接口测试", self.test_authentication_apis),
            ("任务管理接口测试", self.test_task_management_apis),
            ("调度器接口测试", self.test_scheduler_apis),
            ("监控接口测试", self.test_monitoring_apis),
        ]
        
        # 运行测试套件
        for test_name, test_func in test_suites:
            await self.run_test(test_name, test_func)
        
        # 清理测试数据
        await self.run_test("测试数据清理", self.cleanup_test_data)
        
        # 生成测试报告
        await self.generate_test_report()
        
        return True
    
    async def generate_test_report(self):
        """生成测试报告"""
        logger.info("📊 生成测试报告...")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result["success"])
        failed_tests = total_tests - passed_tests
        
        logger.info("=" * 80)
        logger.info("📋 API接口测试报告")
        logger.info("=" * 80)
        
        # 详细结果
        for test_name, result in self.test_results.items():
            status = "✅ 通过" if result["success"] else "❌ 失败"
            duration = result["duration"]
            error = result["error"]
            
            logger.info(f"{status} {test_name:20} (耗时: {duration:.2f}秒)")
            if error:
                logger.info(f"    错误: {error}")
        
        logger.info("-" * 80)
        logger.info(f"总计: {passed_tests}/{total_tests} 测试通过")
        
        if failed_tests > 0:
            logger.warning(f"⚠️ {failed_tests} 个测试失败")
        else:
            logger.success("🎉 所有API接口测试通过！")
        
        logger.info("=" * 80)
        
        # 保存报告到文件
        report_data = {
            "timestamp": time.time(),
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
            },
            "results": self.test_results
        }
        
        try:
            with open("tests/api_test_report.json", "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            logger.success("📄 测试报告已保存到 tests/api_test_report.json")
        except Exception as e:
            logger.warning(f"⚠️ 保存测试报告失败: {e}")


async def main():
    """主函数"""
    from tests.test_utils import TestHelper
    TestHelper.setup_logging()
    
    logger.info("=" * 80)
    logger.info("🔧 数据采集任务管理系统 - 全面API接口测试")
    logger.info("=" * 80)
    
    async with ComprehensiveAPITester() as tester:
        success = await tester.run_all_tests()
        
        return success


if __name__ == "__main__":
    asyncio.run(main())
