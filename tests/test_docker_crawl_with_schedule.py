#!/usr/bin/env python3
"""
Docker爬虫任务和调度完整测试
==========================

测试流程：
1. 登录获取token
2. 创建docker-crawl类型的任务
3. 为任务创建调度（测试用立即执行）
4. 监控任务执行状态
5. 查看容器日志
6. 验证调度功能
7. 清理测试数据

使用方法：
    python tests/test_docker_crawl_with_schedule.py
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode
import httpx
from loguru import logger

# 配置
BASE_URL = "http://localhost:8089"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

class DockerCrawlTester:
    """Docker爬虫任务测试器"""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.token = None
        self.task_id = None
        self.schedule_id = None
        self.execution_id = None
        
        # 测试统计
        self.results = {
            "total": 0,
            "passed": 0,
            "failed": 0
        }
    
    def log_result(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        self.results["total"] += 1
        if success:
            self.results["passed"] += 1
            logger.success(f"✅ {test_name}: {message}")
        else:
            self.results["failed"] += 1
            logger.error(f"❌ {test_name}: {message}")
        return success
    
    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """发送HTTP请求"""
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            return response
    
    async def login(self) -> bool:
        """登录获取token"""
        logger.info("🔐 步骤1: 管理员登录")
        
        try:
            # 先初始化管理员
            await self.request("POST", "/api/v1/user/init-admin")
            
            # 登录
            response = await self.request(
                "POST",
                "/api/v1/auth/login",
                json={
                    "username": ADMIN_USERNAME,
                    "password": ADMIN_PASSWORD
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                # Token在data字段里
                token_data = data.get("data", {})
                self.token = token_data.get("access_token")
                return self.log_result("管理员登录", True, f"登录成功，Token已获取")
            else:
                return self.log_result("管理员登录", False, f"HTTP {response.status_code}")
        except Exception as e:
            return self.log_result("管理员登录", False, str(e))
    
    async def create_docker_crawl_task(self) -> bool:
        """创建docker-crawl类型的任务"""
        logger.info("📋 步骤2: 创建docker-crawl任务")
        
        task_name = f"测试爬虫任务_{int(time.time())}"
        task_data = {
            "task_name": task_name,
            "task_type": "docker-crawl",
            "base_url": "https://httpbin.org/",
            "base_url_params": [
                {
                    "param_name": "page",
                    "param_type": "range",
                    "param_value": "1-3"
                }
            ],
            "need_user_login": 0,
            "extract_config": {
                "extract_method": "api",
                "listened_uri": "/json",
                "extract_dataset_idtf": "test_data",
                "extract_fields": [
                    {
                        "field_name": "slideshow",
                        "field_source_type": "string",
                        "field_source_key": "slideshow",
                        "field_desc": "测试数据"
                    }
                ]
            },
            "description": "这是一个测试用的docker-crawl任务"
        }
        
        try:
            response = await self.request("POST", "/api/v1/task/add", json=task_data)
            
            if response.status_code == 200:
                data = response.json()
                self.task_id = data.get("data", {}).get("task_id")
                return self.log_result(
                    "创建任务",
                    True,
                    f"任务ID: {self.task_id}, 名称: {task_name}"
                )
            else:
                return self.log_result("创建任务", False, f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            return self.log_result("创建任务", False, str(e))
    
    async def create_immediate_schedule(self) -> bool:
        """创建立即执行的调度（用于测试）"""
        logger.info("⏰ 步骤3: 创建调度（立即执行）")
        
        schedule_data = {
            "task_id": self.task_id,
            "schedule_type": "immediate",
            "schedule_config": {}
        }
        
        try:
            response = await self.request("POST", "/api/v1/scheduler/", json=schedule_data)
            
            if response.status_code == 200:
                data = response.json()
                self.schedule_id = data.get("data", {}).get("schedule_id")
                return self.log_result("创建调度", True, f"调度ID: {self.schedule_id}")
            else:
                return self.log_result("创建调度", False, f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            return self.log_result("创建调度", False, str(e))
    
    async def wait_for_execution(self, timeout: int = 60) -> bool:
        """等待任务开始执行"""
        logger.info("⏳ 步骤4: 等待任务开始执行")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = await self.request(
                    "GET",
                    "/api/v1/monitoring/executions/active"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    executions = data.get("data", [])
                    
                    # 查找我们的任务
                    for exe in executions:
                        if exe.get("task_id") == self.task_id:
                            self.execution_id = exe.get("id")
                            return self.log_result(
                                "任务开始执行",
                                True,
                                f"执行ID: {self.execution_id}, 容器: {exe.get('docker_container_name')}"
                            )
                
                # 等待3秒后重试
                await asyncio.sleep(3)
                logger.info("等待任务开始执行...")
            except Exception as e:
                logger.warning(f"检查执行状态出错: {e}")
                await asyncio.sleep(3)
        
        return self.log_result("任务开始执行", False, f"超时{timeout}秒未检测到任务执行")
    
    async def monitor_execution_status(self, max_wait: int = 120) -> bool:
        """监控任务执行状态"""
        logger.info("📊 步骤5: 监控任务执行状态")
        
        if not self.execution_id:
            return self.log_result("监控执行", False, "没有执行ID")
        
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < max_wait:
            try:
                response = await self.request(
                    "GET",
                    f"/api/v1/monitoring/execution/{self.execution_id}/status"
                )
                
                if response.status_code == 200:
                    data = response.json().get("data", {})
                    status = data.get("status")
                    progress = data.get("progress", {})
                    
                    if status != last_status:
                        logger.info(f"状态变更: {status}")
                        if progress:
                            percentage = progress.get("percentage", 0)
                            logger.info(f"进度: {percentage}%")
                        last_status = status
                    
                    # 检查是否完成
                    if status in ["completed", "success"]:
                        return self.log_result(
                            "任务执行完成",
                            True,
                            f"状态: {status}, 耗时: {int(time.time() - start_time)}秒"
                        )
                    elif status in ["failed", "error"]:
                        error = data.get("error_log", "未知错误")
                        return self.log_result("任务执行失败", False, f"错误: {error}")
                
                await asyncio.sleep(5)
            except Exception as e:
                logger.warning(f"获取执行状态出错: {e}")
                await asyncio.sleep(5)
        
        return self.log_result("监控执行", False, f"超时{max_wait}秒，任务未完成")
    
    async def check_execution_history(self) -> bool:
        """检查任务执行历史"""
        logger.info("📜 步骤6: 检查任务执行历史")
        
        try:
            response = await self.request(
                "GET",
                f"/api/v1/task/{self.task_id}/executions?page=1&page_size=10"
            )
            
            if response.status_code == 200:
                data = response.json().get("data", {})
                items = data.get("items", [])
                total = data.get("total", 0)
                
                return self.log_result(
                    "检查执行历史",
                    True,
                    f"共{total}条执行记录，最近{len(items)}条"
                )
            else:
                return self.log_result("检查执行历史", False, f"HTTP {response.status_code}")
        except Exception as e:
            return self.log_result("检查执行历史", False, str(e))
    
    async def test_schedule_types(self) -> bool:
        """测试其他调度类型"""
        logger.info("📅 步骤7: 测试其他调度类型")
        
        # 先删除之前的调度
        if self.schedule_id:
            try:
                await self.request("DELETE", f"/api/v1/scheduler/{self.schedule_id}")
                logger.info(f"删除旧调度: {self.schedule_id}")
            except:
                pass
        
        # 测试每5分钟执行的调度
        schedule_data = {
            "task_id": self.task_id,
            "schedule_type": "minutely",
            "schedule_config": {"interval": 5}
        }
        
        try:
            response = await self.request("POST", "/api/v1/scheduler/", json=schedule_data)
            
            if response.status_code == 200:
                data = response.json()
                new_schedule_id = data.get("data", {}).get("schedule_id")
                
                # 查询调度信息
                response2 = await self.request("GET", f"/api/v1/scheduler/task/{self.task_id}")
                if response2.status_code == 200:
                    schedules = response2.json().get("data", [])
                    if schedules:
                        schedule_info = schedules[0]
                        next_run = schedule_info.get("next_run_time")
                        
                        self.schedule_id = new_schedule_id  # 更新为新的调度ID
                        return self.log_result(
                            "创建定时调度",
                            True,
                            f"每5分钟执行，下次执行: {next_run}"
                        )
                
                return self.log_result("创建定时调度", True, f"调度ID: {new_schedule_id}")
            else:
                return self.log_result("创建定时调度", False, f"HTTP {response.status_code}")
        except Exception as e:
            return self.log_result("创建定时调度", False, str(e))
    
    async def cleanup(self) -> None:
        """清理测试数据"""
        logger.info("🧹 步骤8: 清理测试数据")
        
        # 删除调度
        if self.schedule_id:
            try:
                await self.request("DELETE", f"/api/v1/scheduler/{self.schedule_id}")
                logger.info(f"✅ 删除调度: {self.schedule_id}")
            except Exception as e:
                logger.warning(f"⚠️ 删除调度失败: {e}")
        
        # 删除任务
        if self.task_id:
            try:
                await self.request("DELETE", f"/api/v1/task/{self.task_id}")
                logger.info(f"✅ 删除任务: {self.task_id}")
            except Exception as e:
                logger.warning(f"⚠️ 删除任务失败: {e}")
    
    def print_summary(self):
        """打印测试总结"""
        logger.info("=" * 60)
        logger.info("📊 测试结果总结")
        logger.info("=" * 60)
        logger.info(f"总测试数: {self.results['total']}")
        logger.info(f"✅ 通过: {self.results['passed']}")
        logger.info(f"❌ 失败: {self.results['failed']}")
        
        if self.results['total'] > 0:
            success_rate = (self.results['passed'] / self.results['total'] * 100)
            logger.info(f"📈 成功率: {success_rate:.1f}%")
        
        if self.results['failed'] == 0:
            logger.success("🎉 所有测试通过！")
        else:
            logger.warning(f"⚠️ 有 {self.results['failed']} 个测试失败")
    
    async def run_full_test(self):
        """运行完整测试流程"""
        logger.info("🚀 开始Docker爬虫任务和调度完整测试")
        logger.info(f"🌐 测试服务器: {self.base_url}")
        logger.info("=" * 60)
        
        try:
            # 1. 登录
            if not await self.login():
                logger.error("登录失败，终止测试")
                return
            
            # 2. 创建任务
            if not await self.create_docker_crawl_task():
                logger.error("创建任务失败，终止测试")
                return
            
            # 3. 创建立即执行的调度
            if not await self.create_immediate_schedule():
                logger.error("创建调度失败，继续其他测试")
            
            # 4. 等待任务开始执行（给调度器一些时间）
            logger.info("等待调度器触发任务...")
            await asyncio.sleep(10)  # 等待10秒让Celery Beat触发
            
            await self.wait_for_execution(timeout=60)
            
            # 5. 监控执行状态
            if self.execution_id:
                await self.monitor_execution_status(max_wait=120)
            
            # 6. 检查执行历史
            await self.check_execution_history()
            
            # 7. 测试其他调度类型
            await self.test_schedule_types()
            
        except Exception as e:
            logger.error(f"测试过程中发生异常: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # 8. 清理测试数据
            await self.cleanup()
            
            # 打印总结
            self.print_summary()
        
        return self.results['failed'] == 0


async def main():
    """主函数"""
    tester = DockerCrawlTester()
    success = await tester.run_full_test()
    
    import sys
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

