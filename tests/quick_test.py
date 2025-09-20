#!/usr/bin/env python3
"""
数据采集任务管理系统 - 快速测试脚本
====================================

这是一个简化的测试脚本，用于快速验证系统的基本功能。

使用方法：
    python quick_test.py
"""

import asyncio
import json
import time
import httpx
from loguru import logger


async def quick_test():
    """快速测试系统基本功能"""
    logger.info("🚀 开始快速测试...")
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 1. 测试系统根路径
            logger.info("1️⃣ 测试系统根路径...")
            response = await client.get(f"{base_url}/api/v1/")
            logger.success(f"✅ 系统响应: {response.json()}")
            
            # 2. 测试API文档
            logger.info("2️⃣ 测试API文档...")
            response = await client.get(f"{base_url}/docs")
            if response.status_code == 200:
                logger.success("✅ API文档可访问")
            else:
                logger.warning(f"⚠️ API文档状态码: {response.status_code}")
            
            # 3. 测试用户注册
            logger.info("3️⃣ 测试用户注册...")
            test_user = {
                "username": f"quick_test_{int(time.time())}",
                "email": f"quick_test_{int(time.time())}@example.com",
                "password": "QuickTest123!",
                "full_name": "快速测试用户"
            }
            
            response = await client.post(
                f"{base_url}/api/v1/user/add",
                json=test_user
            )
            
            if response.status_code == 201:
                user_data = response.json()
                logger.success(f"✅ 用户注册成功: {user_data['username']}")
                
                # 4. 测试用户登录
                logger.info("4️⃣ 测试用户登录...")
                login_data = {
                    "username": test_user["username"],
                    "password": test_user["password"]
                }
                
                response = await client.post(
                    f"{base_url}/api/v1/auth/token",
                    data=login_data
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    access_token = token_data["access_token"]
                    logger.success("✅ 用户登录成功")
                    
                    # 5. 测试创建任务
                    logger.info("5️⃣ 测试创建任务...")
                    headers = {"Authorization": f"Bearer {access_token}"}
                    
                    task_data = {
                        "task_name": f"快速测试任务_{int(time.time())}",
                        "task_type": "api",
                        "description": "快速测试任务",
                        "base_url": "https://httpbin.org/json",
                        "base_url_params": {},
                        "need_user_login": False,
                        "extract_config": {
                            "method": "GET"
                        }
                    }
                    
                    response = await client.post(
                        f"{base_url}/api/v1/task/",
                        json=task_data,
                        headers=headers
                    )
                    
                    if response.status_code == 201:
                        task_result = response.json()
                        logger.success(f"✅ 任务创建成功: {task_result['task_name']}")
                        
                        # 6. 测试获取任务列表
                        logger.info("6️⃣ 测试获取任务列表...")
                        response = await client.get(
                            f"{base_url}/api/v1/task/",
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            tasks = response.json()
                            logger.success(f"✅ 获取任务列表成功: 共{len(tasks['items'])}个任务")
                        else:
                            logger.warning(f"⚠️ 获取任务列表失败: {response.status_code}")
                        
                        # 7. 清理测试数据
                        logger.info("7️⃣ 清理测试数据...")
                        await client.delete(
                            f"{base_url}/api/v1/task/{task_result['id']}",
                            headers=headers
                        )
                        await client.delete(
                            f"{base_url}/api/v1/user/{user_data['id']}",
                            headers=headers
                        )
                        logger.success("✅ 测试数据清理完成")
                        
                    else:
                        logger.warning(f"⚠️ 任务创建失败: {response.status_code}")
                else:
                    logger.warning(f"⚠️ 用户登录失败: {response.status_code}")
            else:
                logger.warning(f"⚠️ 用户注册失败: {response.status_code}")
            
            logger.success("🎉 快速测试完成！")
            
        except Exception as e:
            logger.error(f"❌ 测试过程中出现错误: {e}")
            return False
    
    return True


async def main():
    """主函数"""
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    
    logger.info("=" * 50)
    logger.info("🔧 数据采集任务管理系统 - 快速测试")
    logger.info("=" * 50)
    
    success = await quick_test()
    
    logger.info("=" * 50)
    if success:
        logger.success("🎉 快速测试通过！系统基本功能正常！")
    else:
        logger.error("❌ 快速测试失败！请检查系统状态！")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
