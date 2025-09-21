#!/usr/bin/env python3
"""
主要接口测试运行脚本
==================

快速运行主要API接口测试

使用方法：
    python tests/run_main_tests.py
    python tests/run_main_tests.py --no-cleanup
    python tests/run_main_tests.py --verbose
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.main_api_test import MainAPITester
from tests.test_config import config
from loguru import logger


async def run_tests():
    """运行主要接口测试"""
    logger.info("🚀 启动主要接口测试...")
    
    # 检查服务器是否运行
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config.BASE_URL}/api/v1/", timeout=5.0)
            if response.status_code != 200:
                logger.error(f"❌ 服务器响应异常: HTTP {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"❌ 无法连接到服务器 {config.BASE_URL}: {e}")
        logger.info("💡 请确保服务器正在运行: pdm run start")
        return False
    
    # 创建测试器并运行测试
    tester = MainAPITester()
    success = await tester.run_all_tests()
    
    return success


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="主要接口测试运行脚本")
    parser.add_argument("--base-url", default=config.BASE_URL, help="测试服务器地址")
    parser.add_argument("--no-cleanup", action="store_true", help="不清理测试数据")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 配置日志
    if args.verbose:
        logger.remove()
        logger.add(sys.stdout, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    
    # 运行测试
    try:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("⚠️ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 测试运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
