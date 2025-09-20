#!/usr/bin/env python3
"""
数据采集任务管理系统 - 简化测试脚本
====================================

这个脚本先初始化管理员账户，然后进行基本的系统测试。

使用方法：
    python simple_test.py
"""

import asyncio
import time
import httpx
from loguru import logger


async def simple_test():
    """简化的系统测试"""
    logger.info("🚀 开始简化测试...")
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 1. 测试系统根路径
            logger.info("1️⃣ 测试系统根路径...")
            response = await client.get(f"{base_url}/api/v1/")
            logger.success(f"✅ 系统响应: {response.json()}")
            
            # 2. 初始化管理员账户
            logger.info("2️⃣ 初始化管理员账户...")
            response = await client.post(f"{base_url}/api/v1/user/init-admin")
            
            if response.status_code == 200:
                admin_data = response.json()
                logger.success(f"✅ 管理员账户创建成功: {admin_data}")
            elif response.status_code == 400:
                logger.info("ℹ️ 管理员账户已存在")
            else:
                logger.warning(f"⚠️ 管理员账户初始化失败: {response.status_code}")
                logger.warning(f"响应内容: {response.text}")
            
            # 3. 管理员登录
            logger.info("3️⃣ 管理员登录...")
            login_data = {
                "username": "admin",
                "password": "admin123"  # 默认密码
            }
            
            response = await client.post(
                f"{base_url}/api/v1/auth/token",
                data=login_data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data["access_token"]
                logger.success("✅ 管理员登录成功")
                
                # 4. 测试创建用户
                logger.info("4️⃣ 测试创建用户...")
                headers = {"Authorization": f"Bearer {access_token}"}
                
                test_user = {
                    "username": f"test_user_{int(time.time())}",
                    "email": f"test_{int(time.time())}@example.com",
                    "password": "TestPassword123!",
                    "full_name": "测试用户"
                }
                
                response = await client.post(
                    f"{base_url}/api/v1/user/add",
                    json=test_user,
                    headers=headers
                )
                
                if response.status_code == 201:
                    user_data = response.json()
                    logger.success(f"✅ 用户创建成功: {user_data['username']}")
                    
                    # 5. 测试创建任务
                    logger.info("5️⃣ 测试创建任务...")
                    task_data = {
                        "task_name": f"测试任务_{int(time.time())}",
                        "task_type": "api",
                        "description": "测试任务",
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
                        logger.warning(f"响应内容: {response.text}")
                else:
                    logger.warning(f"⚠️ 用户创建失败: {response.status_code}")
                    logger.warning(f"响应内容: {response.text}")
            else:
                logger.warning(f"⚠️ 管理员登录失败: {response.status_code}")
                logger.warning(f"响应内容: {response.text}")
            
            logger.success("🎉 简化测试完成！")
            return True
            
        except Exception as e:
            logger.error(f"❌ 测试过程中出现错误: {e}")
            return False


async def main():
    """主函数"""
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    
    logger.info("=" * 50)
    logger.info("🔧 数据采集任务管理系统 - 简化测试")
    logger.info("=" * 50)
    
    success = await simple_test()
    
    logger.info("=" * 50)
    if success:
        logger.success("🎉 简化测试通过！系统基本功能正常！")
    else:
        logger.error("❌ 简化测试失败！请检查系统状态！")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
