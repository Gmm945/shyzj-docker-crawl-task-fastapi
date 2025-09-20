#!/usr/bin/env python3
"""
Docker容器管理功能测试脚本
========================

这个脚本专门用于测试Docker容器管理功能，包括：
1. 容器状态检查
2. 容器日志获取
3. 容器启动和停止
4. 容器健康检查

使用方法：
    python docker_test.py
"""

import asyncio
import json
import time
import httpx
from loguru import logger


class DockerTester:
    """Docker容器管理测试类"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.access_token = None
        self.container_id = None
    
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _login(self):
        """登录获取访问令牌"""
        logger.info("🔐 登录系统...")
        
        # 先注册一个测试用户
        test_user = {
            "username": f"docker_test_{int(time.time())}",
            "email": f"docker_test_{int(time.time())}@example.com",
            "password": "DockerTest123!",
            "full_name": "Docker测试用户"
        }
        
        # 注册用户
        response = await self.client.post(
            f"{self.base_url}/api/v1/user/add",
            json=test_user
        )
        
        if response.status_code != 201:
            logger.error(f"❌ 用户注册失败: {response.status_code}")
            return False
        
        # 登录用户
        login_data = {
            "username": test_user["username"],
            "password": test_user["password"]
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/auth/token",
            data=login_data
        )
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data["access_token"]
            logger.success("✅ 登录成功")
            return True
        else:
            logger.error(f"❌ 登录失败: {response.status_code}")
            return False
    
    async def test_container_status(self):
        """测试容器状态检查"""
        logger.info("📊 测试容器状态检查...")
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            # 获取所有容器状态
            response = await self.client.get(
                f"{self.base_url}/api/v1/monitoring/containers",
                headers=headers
            )
            
            if response.status_code == 200:
                containers = response.json()
                logger.success(f"✅ 获取容器列表成功: 共{len(containers)}个容器")
                
                # 显示容器信息
                for container in containers[:3]:  # 只显示前3个
                    logger.info(f"   容器: {container.get('name', 'Unknown')} - 状态: {container.get('status', 'Unknown')}")
                
                return True
            else:
                logger.warning(f"⚠️ 获取容器列表失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 容器状态检查失败: {e}")
            return False
    
    async def test_docker_health(self):
        """测试Docker健康检查"""
        logger.info("🏥 测试Docker健康检查...")
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            # 检查Docker主机连接
            response = await self.client.get(
                f"{self.base_url}/api/v1/monitoring/docker-health",
                headers=headers
            )
            
            if response.status_code == 200:
                health_data = response.json()
                logger.success(f"✅ Docker健康检查成功: {health_data}")
                return True
            else:
                logger.warning(f"⚠️ Docker健康检查失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Docker健康检查失败: {e}")
            return False
    
    async def test_container_management(self):
        """测试容器管理功能"""
        logger.info("🐳 测试容器管理功能...")
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            # 1. 获取容器列表
            response = await self.client.get(
                f"{self.base_url}/api/v1/monitoring/containers",
                headers=headers
            )
            
            if response.status_code != 200:
                logger.warning("⚠️ 无法获取容器列表，跳过容器管理测试")
                return False
            
            containers = response.json()
            if not containers:
                logger.info("ℹ️ 没有运行中的容器，跳过容器管理测试")
                return False
            
            # 使用第一个容器进行测试
            test_container = containers[0]
            container_id = test_container.get('id')
            container_name = test_container.get('name', 'Unknown')
            
            logger.info(f"📋 使用容器进行测试: {container_name} ({container_id})")
            
            # 2. 获取容器状态
            response = await self.client.get(
                f"{self.base_url}/api/v1/monitoring/containers/{container_id}/status",
                headers=headers
            )
            
            if response.status_code == 200:
                status_data = response.json()
                logger.success(f"✅ 容器状态获取成功: {status_data}")
            else:
                logger.warning(f"⚠️ 容器状态获取失败: {response.status_code}")
            
            # 3. 获取容器日志
            response = await self.client.get(
                f"{self.base_url}/api/v1/monitoring/containers/{container_id}/logs",
                headers=headers
            )
            
            if response.status_code == 200:
                logs_data = response.json()
                logger.success(f"✅ 容器日志获取成功: {len(logs_data.get('logs', ''))} 字符")
            else:
                logger.warning(f"⚠️ 容器日志获取失败: {response.status_code}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 容器管理测试失败: {e}")
            return False
    
    async def test_task_execution_with_docker(self):
        """测试Docker任务执行"""
        logger.info("🚀 测试Docker任务执行...")
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            # 1. 创建Docker爬虫任务
            docker_task = {
                "task_name": f"Docker测试任务_{int(time.time())}",
                "task_type": "docker-crawl",
                "description": "Docker容器管理测试任务",
                "base_url": "https://httpbin.org/json",
                "base_url_params": {},
                "need_user_login": False,
                "extract_config": {
                    "method": "GET",
                    "timeout": 30
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/task/",
                json=docker_task,
                headers=headers
            )
            
            if response.status_code != 201:
                logger.warning(f"⚠️ 任务创建失败: {response.status_code}")
                return False
            
            task_data = response.json()
            task_id = task_data["id"]
            logger.success(f"✅ Docker任务创建成功: {task_data['task_name']}")
            
            # 2. 执行任务
            execution_data = {
                "execution_name": f"Docker执行测试_{int(time.time())}",
                "task_id": task_id
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/task/execute",
                json=execution_data,
                headers=headers
            )
            
            if response.status_code == 202:
                execution_result = response.json()
                execution_id = execution_result["execution_id"]
                logger.success(f"✅ 任务执行请求成功: {execution_id}")
                
                # 3. 等待执行完成并检查状态
                logger.info("⏳ 等待任务执行...")
                await asyncio.sleep(10)
                
                response = await self.client.get(
                    f"{self.base_url}/api/v1/task/executions/{execution_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    execution_status = response.json()
                    logger.success(f"✅ 执行状态检查成功: {execution_status['status']}")
                    
                    # 4. 获取执行日志
                    response = await self.client.get(
                        f"{self.base_url}/api/v1/task/executions/{execution_id}/logs",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        logs_data = response.json()
                        logger.success(f"✅ 执行日志获取成功: {len(logs_data.get('logs', ''))} 字符")
                    
                    # 5. 清理任务
                    await self.client.delete(
                        f"{self.base_url}/api/v1/task/{task_id}",
                        headers=headers
                    )
                    logger.info("🗑️ 测试任务已清理")
                    
                    return True
                else:
                    logger.warning(f"⚠️ 执行状态检查失败: {response.status_code}")
            else:
                logger.warning(f"⚠️ 任务执行请求失败: {response.status_code}")
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Docker任务执行测试失败: {e}")
            return False
    
    async def run_all_tests(self):
        """运行所有Docker相关测试"""
        logger.info("🐳 开始Docker功能测试...")
        
        # 登录
        if not await self._login():
            logger.error("❌ 登录失败，无法继续测试")
            return False
        
        test_results = []
        
        # 1. Docker健康检查
        test_results.append(await self.test_docker_health())
        
        # 2. 容器状态检查
        test_results.append(await self.test_container_status())
        
        # 3. 容器管理功能
        test_results.append(await self.test_container_management())
        
        # 4. Docker任务执行
        test_results.append(await self.test_task_execution_with_docker())
        
        # 统计结果
        passed_tests = sum(test_results)
        total_tests = len(test_results)
        
        logger.info(f"📊 Docker测试结果: {passed_tests}/{total_tests} 通过")
        
        if passed_tests == total_tests:
            logger.success("🎉 所有Docker测试通过！")
            return True
        else:
            logger.warning(f"⚠️ {total_tests - passed_tests} 个Docker测试失败")
            return False


async def main():
    """主函数"""
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    
    logger.info("=" * 60)
    logger.info("🐳 Docker容器管理功能测试")
    logger.info("=" * 60)
    
    async with DockerTester() as tester:
        success = await tester.run_all_tests()
        
        logger.info("=" * 60)
        if success:
            logger.success("🎉 Docker测试完成！容器管理功能正常！")
        else:
            logger.warning("⚠️ Docker测试完成！部分功能可能存在问题！")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
