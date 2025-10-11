#!/usr/bin/env python3
"""
调度任务测试脚本
===============

全面测试任务调度功能，包括：
1. 各种调度类型的创建和验证
2. 下次执行时间计算
3. 调度启用/禁用
4. 调度查询和删除
5. 边界条件测试

使用方法：
    python tests/test_scheduler.py
    python tests/test_scheduler.py --verbose
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

import httpx
from loguru import logger

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_config import config
from tests.test_utils import TestHTTPClient, AuthManager
from src.utils.schedule_utils import ScheduleUtils
from src.data_platform_api.models.task import ScheduleType


class SchedulerTester:
    """调度器测试类"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.BASE_URL
        self.client = TestHTTPClient(self.base_url)
        self.auth_manager = AuthManager(self.client)
        
        # 测试数据存储
        self.test_task_id = None
        self.created_schedules = []
        
        # 测试结果统计
        self.test_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
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
    
    async def setup(self):
        """设置测试环境"""
        logger.info("🔧 设置测试环境...")
        
        # 1. 初始化管理员账户并登录
        try:
            await self.client.post("/api/v1/user/init-admin")
            await self.auth_manager.login_admin()
            logger.info("✅ 管理员登录成功")
        except Exception as e:
            logger.error(f"❌ 管理员登录失败: {e}")
            return False
        
        # 2. 创建测试任务
        try:
            task_data = config.get_test_task_data("api_task")
            response = await self.client.post("/api/v1/task/add", json=task_data)
            if response.status_code == 200:
                task_info = response.json()
                self.test_task_id = task_info.get("data", {}).get("task_id")
                logger.info(f"✅ 测试任务创建成功: {self.test_task_id}")
                return True
            else:
                logger.error(f"❌ 创建测试任务失败: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ 创建测试任务异常: {e}")
            return False
    
    async def cleanup(self):
        """清理测试数据"""
        logger.info("🧹 清理测试数据...")
        
        # 删除创建的调度
        for schedule_id in self.created_schedules:
            try:
                await self.client.delete(f"/api/v1/scheduler/{schedule_id}")
                logger.info(f"✅ 删除调度: {schedule_id}")
            except Exception as e:
                logger.warning(f"⚠️ 删除调度失败 {schedule_id}: {e}")
        
        # 删除测试任务
        if self.test_task_id:
            try:
                await self.client.delete(f"/api/v1/task/{self.test_task_id}")
                logger.info(f"✅ 删除测试任务: {self.test_task_id}")
            except Exception as e:
                logger.warning(f"⚠️ 删除测试任务失败: {e}")
    
    async def test_schedule_config_validation(self):
        """测试调度配置验证"""
        logger.info("📝 测试调度配置验证...")
        
        test_cases = [
            # 立即执行
            (ScheduleType.IMMEDIATE, {}, True, "立即执行配置"),
            
            # 定时执行
            (ScheduleType.SCHEDULED, {"datetime": "2025-12-31 23:59:59"}, True, "定时执行有效配置"),
            (ScheduleType.SCHEDULED, {}, False, "定时执行缺少datetime"),
            (ScheduleType.SCHEDULED, {"datetime": "invalid"}, False, "定时执行无效时间格式"),
            
            # 分钟级调度
            (ScheduleType.MINUTELY, {"interval": 5}, True, "分钟级有效配置"),
            (ScheduleType.MINUTELY, {"interval": 0}, False, "分钟级interval为0"),
            (ScheduleType.MINUTELY, {"interval": -1}, False, "分钟级interval为负数"),
            
            # 小时级调度
            (ScheduleType.HOURLY, {"interval": 2}, True, "小时级有效配置"),
            (ScheduleType.HOURLY, {"interval": 0}, False, "小时级interval为0"),
            
            # 每日调度
            (ScheduleType.DAILY, {"time": "09:00:00"}, True, "每日有效配置"),
            (ScheduleType.DAILY, {}, False, "每日缺少time"),
            (ScheduleType.DAILY, {"time": "25:00:00"}, False, "每日无效时间"),
            
            # 周调度
            (ScheduleType.WEEKLY, {"days": [1, 3, 5], "time": "09:00:00"}, True, "周调度有效配置"),
            (ScheduleType.WEEKLY, {"days": [1, 3, 5]}, False, "周调度缺少time"),
            (ScheduleType.WEEKLY, {"time": "09:00:00"}, False, "周调度缺少days"),
            (ScheduleType.WEEKLY, {"days": [0, 8], "time": "09:00:00"}, False, "周调度days超出范围"),
            
            # 月调度
            (ScheduleType.MONTHLY, {"dates": [1, 15], "time": "10:00:00"}, True, "月调度有效配置"),
            (ScheduleType.MONTHLY, {"dates": [1, 15]}, False, "月调度缺少time"),
            (ScheduleType.MONTHLY, {"time": "10:00:00"}, False, "月调度缺少dates"),
            (ScheduleType.MONTHLY, {"dates": [0, 32], "time": "10:00:00"}, False, "月调度dates超出范围"),
        ]
        
        for schedule_type, config, expected_valid, desc in test_cases:
            is_valid, message = ScheduleUtils.validate_schedule_config(schedule_type, config)
            success = is_valid == expected_valid
            self.log_test_result(
                f"配置验证-{desc}",
                success,
                message if success else f"期望{expected_valid}但得到{is_valid}: {message}"
            )
    
    async def test_next_run_time_calculation(self):
        """测试下次执行时间计算"""
        logger.info("🕐 测试下次执行时间计算...")
        
        now = datetime.now()
        
        # 立即执行
        next_time = ScheduleUtils.calculate_next_run_time(ScheduleType.IMMEDIATE, {})
        success = next_time is not None and abs((next_time - now).total_seconds()) < 2
        self.log_test_result("立即执行时间计算", success, f"下次执行: {next_time}")
        
        # 分钟级调度
        next_time = ScheduleUtils.calculate_next_run_time(ScheduleType.MINUTELY, {"interval": 5})
        expected = now + timedelta(minutes=5)
        success = next_time is not None and abs((next_time - expected).total_seconds()) < 2
        self.log_test_result("分钟级调度时间计算", success, f"下次执行: {next_time}")
        
        # 小时级调度
        next_time = ScheduleUtils.calculate_next_run_time(ScheduleType.HOURLY, {"interval": 2})
        expected = now + timedelta(hours=2)
        success = next_time is not None and abs((next_time - expected).total_seconds()) < 2
        self.log_test_result("小时级调度时间计算", success, f"下次执行: {next_time}")
        
        # 每日调度 - 明天9点
        next_time = ScheduleUtils.calculate_next_run_time(ScheduleType.DAILY, {"time": "09:00:00"})
        success = next_time is not None
        if success:
            # 应该是今天或明天的9点
            success = next_time.hour == 9 and next_time > now
        self.log_test_result("每日调度时间计算", success, f"下次执行: {next_time}")
        
        # 周调度 - 每周一、三、五 09:00
        next_time = ScheduleUtils.calculate_next_run_time(
            ScheduleType.WEEKLY,
            {"days": [1, 3, 5], "time": "09:00:00"}
        )
        success = next_time is not None
        if success:
            # 应该是未来的时间，且是周一、三、五之一
            success = next_time > now and next_time.weekday() + 1 in [1, 3, 5]
        self.log_test_result("周调度时间计算", success, f"下次执行: {next_time}")
        
        # 月调度 - 每月1号和15号 10:00
        next_time = ScheduleUtils.calculate_next_run_time(
            ScheduleType.MONTHLY,
            {"dates": [1, 15], "time": "10:00:00"}
        )
        success = next_time is not None
        if success:
            # 应该是未来的时间，且是1号或15号
            success = next_time > now and next_time.day in [1, 15]
        self.log_test_result("月调度时间计算", success, f"下次执行: {next_time}")
        
        # 定时执行 - 过去的时间应该返回None
        past_time = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        next_time = ScheduleUtils.calculate_next_run_time(
            ScheduleType.SCHEDULED,
            {"datetime": past_time}
        )
        success = next_time is None
        self.log_test_result("定时执行-过去时间", success, "返回None")
        
        # 定时执行 - 未来的时间
        future_time = (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        next_time = ScheduleUtils.calculate_next_run_time(
            ScheduleType.SCHEDULED,
            {"datetime": future_time}
        )
        success = next_time is not None and next_time > now
        self.log_test_result("定时执行-未来时间", success, f"下次执行: {next_time}")
    
    async def test_create_schedule(self, schedule_type: ScheduleType, config: dict, description: str):
        """测试创建调度"""
        try:
            schedule_data = {
                "task_id": self.test_task_id,
                "schedule_type": schedule_type.value,
                "schedule_config": config
            }
            
            response = await self.client.post("/api/v1/scheduler/", json=schedule_data)
            
            if response.status_code == 200:
                result = response.json()
                schedule_id = result.get("data", {}).get("schedule_id")
                if schedule_id:
                    self.created_schedules.append(schedule_id)
                    self.log_test_result(f"创建调度-{description}", True, f"调度ID: {schedule_id}")
                    return schedule_id
                else:
                    self.log_test_result(f"创建调度-{description}", False, "未返回调度ID")
                    return None
            else:
                self.log_test_result(f"创建调度-{description}", False, f"HTTP {response.status_code}: {response.text}")
                return None
        except Exception as e:
            self.log_test_result(f"创建调度-{description}", False, str(e))
            return None
    
    async def test_create_all_schedule_types(self):
        """测试创建所有类型的调度"""
        logger.info("📅 测试创建各种类型的调度...")
        
        # 1. 立即执行
        await self.test_create_schedule(ScheduleType.IMMEDIATE, {}, "立即执行")
        
        # 等待一秒，避免冲突（因为immediate会马上执行，任务可能还在运行）
        await asyncio.sleep(1)
        
        # 删除立即执行的调度，因为它会与其他调度冲突
        if self.created_schedules:
            schedule_id = self.created_schedules[-1]
            await self.client.delete(f"/api/v1/scheduler/{schedule_id}")
            self.created_schedules.pop()
        
        # 2. 分钟级调度 - 每5分钟
        await self.test_create_schedule(
            ScheduleType.MINUTELY,
            {"interval": 5},
            "每5分钟执行"
        )
        
        # 删除以便测试下一个
        if self.created_schedules:
            await self.client.delete(f"/api/v1/scheduler/{self.created_schedules[-1]}")
            self.created_schedules.pop()
        
        # 3. 小时级调度 - 每2小时
        await self.test_create_schedule(
            ScheduleType.HOURLY,
            {"interval": 2},
            "每2小时执行"
        )
        
        if self.created_schedules:
            await self.client.delete(f"/api/v1/scheduler/{self.created_schedules[-1]}")
            self.created_schedules.pop()
        
        # 4. 每日调度 - 每天9点
        await self.test_create_schedule(
            ScheduleType.DAILY,
            {"time": "09:00:00"},
            "每天9点执行"
        )
        
        if self.created_schedules:
            await self.client.delete(f"/api/v1/scheduler/{self.created_schedules[-1]}")
            self.created_schedules.pop()
        
        # 5. 周调度 - 每周一、三、五 9点
        await self.test_create_schedule(
            ScheduleType.WEEKLY,
            {"days": [1, 3, 5], "time": "09:00:00"},
            "每周一三五9点执行"
        )
        
        if self.created_schedules:
            await self.client.delete(f"/api/v1/scheduler/{self.created_schedules[-1]}")
            self.created_schedules.pop()
        
        # 6. 月调度 - 每月1号和15号 10点
        schedule_id = await self.test_create_schedule(
            ScheduleType.MONTHLY,
            {"dates": [1, 15], "time": "10:00:00"},
            "每月1号15号10点执行"
        )
        
        # 保留最后一个用于后续测试
        return schedule_id
    
    async def test_duplicate_schedule(self):
        """测试重复创建调度（应该失败）"""
        logger.info("🔄 测试重复创建调度...")
        
        # 尝试再创建一个调度（应该失败，因为已经有活跃调度）
        try:
            schedule_data = {
                "task_id": self.test_task_id,
                "schedule_type": ScheduleType.DAILY.value,
                "schedule_config": {"time": "10:00:00"}
            }
            
            response = await self.client.post("/api/v1/scheduler/", json=schedule_data)
            
            # 应该返回400错误
            success = response.status_code == 400
            self.log_test_result(
                "重复创建调度",
                success,
                "正确拒绝重复调度" if success else f"未拒绝重复调度: HTTP {response.status_code}"
            )
        except Exception as e:
            self.log_test_result("重复创建调度", False, str(e))
    
    async def test_query_schedule(self):
        """测试查询调度"""
        logger.info("🔍 测试查询调度...")
        
        try:
            response = await self.client.get(f"/api/v1/scheduler/task/{self.test_task_id}")
            
            if response.status_code == 200:
                result = response.json()
                schedules = result.get("data", [])
                
                # 应该有至少一个调度
                success = len(schedules) > 0
                self.log_test_result(
                    "查询任务调度",
                    success,
                    f"找到 {len(schedules)} 个调度" if success else "未找到调度"
                )
                
                # 验证调度字段
                if schedules:
                    schedule = schedules[0]
                    has_required_fields = all(
                        field in schedule
                        for field in ["id", "task_id", "schedule_type", "schedule_config", "is_active"]
                    )
                    self.log_test_result(
                        "调度字段完整性",
                        has_required_fields,
                        "所有必需字段存在" if has_required_fields else "缺少必需字段"
                    )
            else:
                self.log_test_result("查询任务调度", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("查询任务调度", False, str(e))
    
    async def test_toggle_schedule(self):
        """测试启用/禁用调度"""
        logger.info("🔀 测试启用/禁用调度...")
        
        if not self.created_schedules:
            self.log_test_result("启用/禁用调度", False, "没有可用的调度ID")
            return
        
        schedule_id = self.created_schedules[-1]
        
        try:
            # 第一次切换（禁用）
            response = await self.client.put(f"/api/v1/scheduler/{schedule_id}/toggle")
            success = response.status_code == 200
            self.log_test_result("禁用调度", success, "禁用成功" if success else f"HTTP {response.status_code}")
            
            # 第二次切换（启用）
            response = await self.client.put(f"/api/v1/scheduler/{schedule_id}/toggle")
            success = response.status_code == 200
            self.log_test_result("启用调度", success, "启用成功" if success else f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("启用/禁用调度", False, str(e))
    
    async def test_delete_schedule(self):
        """测试删除调度"""
        logger.info("🗑️ 测试删除调度...")
        
        if not self.created_schedules:
            self.log_test_result("删除调度", False, "没有可用的调度ID")
            return
        
        schedule_id = self.created_schedules[-1]
        
        try:
            response = await self.client.delete(f"/api/v1/scheduler/{schedule_id}")
            success = response.status_code == 200
            self.log_test_result("删除调度", success, "删除成功" if success else f"HTTP {response.status_code}")
            
            if success:
                self.created_schedules.pop()
        except Exception as e:
            self.log_test_result("删除调度", False, str(e))
    
    async def test_edge_cases(self):
        """测试边界条件"""
        logger.info("🔬 测试边界条件...")
        
        # 1. 无效的任务ID
        try:
            invalid_task_id = "00000000-0000-0000-0000-000000000000"
            schedule_data = {
                "task_id": invalid_task_id,
                "schedule_type": ScheduleType.DAILY.value,
                "schedule_config": {"time": "09:00:00"}
            }
            response = await self.client.post("/api/v1/scheduler/", json=schedule_data)
            success = response.status_code in [404, 400]
            self.log_test_result("无效任务ID", success, "正确拒绝" if success else f"未拒绝: HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("无效任务ID", False, str(e))
        
        # 2. 无效的调度类型
        try:
            schedule_data = {
                "task_id": self.test_task_id,
                "schedule_type": "invalid_type",
                "schedule_config": {}
            }
            response = await self.client.post("/api/v1/scheduler/", json=schedule_data)
            success = response.status_code in [422, 400]
            self.log_test_result("无效调度类型", success, "正确拒绝" if success else f"未拒绝: HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("无效调度类型", False, str(e))
        
        # 3. 查询不存在的调度
        try:
            fake_schedule_id = "fake_schedule_id"
            response = await self.client.get(f"/api/v1/scheduler/task/{fake_schedule_id}")
            # 这个应该返回空列表或404
            success = response.status_code in [200, 404]
            self.log_test_result("查询不存在的调度", success, "正确处理" if success else f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test_result("查询不存在的调度", False, str(e))
    
    def print_test_summary(self):
        """打印测试总结"""
        logger.info("=" * 60)
        logger.info("📊 调度任务测试结果总结")
        logger.info("=" * 60)
        logger.info(f"总测试数: {self.test_results['total']}")
        logger.info(f"✅ 通过: {self.test_results['passed']}")
        logger.info(f"❌ 失败: {self.test_results['failed']}")
        
        if self.test_results['total'] > 0:
            success_rate = (self.test_results['passed'] / self.test_results['total'] * 100)
            logger.info(f"📈 成功率: {success_rate:.1f}%")
        
        if self.test_results['failed'] == 0:
            logger.success("🎉 所有测试通过！")
        else:
            logger.warning(f"⚠️ 有 {self.test_results['failed']} 个测试失败")
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始调度任务测试...")
        logger.info(f"🌐 测试服务器: {self.base_url}")
        
        try:
            # 设置测试环境
            if not await self.setup():
                logger.error("测试环境设置失败，终止测试")
                return False
            
            # 运行测试
            await self.test_schedule_config_validation()
            await self.test_next_run_time_calculation()
            await self.test_create_all_schedule_types()
            await self.test_duplicate_schedule()
            await self.test_query_schedule()
            await self.test_toggle_schedule()
            await self.test_delete_schedule()
            await self.test_edge_cases()
            
        except Exception as e:
            logger.error(f"测试过程中发生异常: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # 清理测试数据
            await self.cleanup()
            
            # 打印测试总结
            self.print_test_summary()
        
        return self.test_results['failed'] == 0


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="调度任务测试脚本")
    parser.add_argument("--base-url", default=config.BASE_URL, help="测试服务器地址")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 配置日志
    if args.verbose:
        logger.remove()
        logger.add(sys.stdout, level="DEBUG")
    
    # 创建测试器并运行测试
    tester = SchedulerTester(args.base_url)
    success = await tester.run_all_tests()
    
    # 退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

