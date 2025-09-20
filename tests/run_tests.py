#!/usr/bin/env python3
"""
测试运行器 - 统一的测试入口
==========================

这个脚本提供了一个统一的入口来运行各种测试，支持：
1. 单个测试脚本运行
2. 批量测试运行
3. 测试结果汇总
4. 测试配置管理

使用方法：
    python tests/run_tests.py                    # 运行所有测试
    python tests/run_tests.py --quick            # 只运行快速测试
    python tests/run_tests.py --simple           # 只运行简化测试
    python tests/run_tests.py --docker           # 只运行Docker测试
    python tests/run_tests.py --full             # 运行完整测试
    python tests/run_tests.py --list             # 列出所有可用测试
"""

import asyncio
import argparse
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger


class TestRunner:
    """测试运行器类"""
    
    def __init__(self):
        self.test_scripts = {
            "simple": "simple_test.py",
            "quick": "quick_test.py", 
            "docker": "docker_test.py",
            "full": "test_examples.py",
            "comprehensive": "comprehensive_api_test.py"
        }
        self.results: Dict[str, bool] = {}
    
    def list_tests(self):
        """列出所有可用的测试"""
        logger.info("📋 可用的测试脚本：")
        logger.info("=" * 50)
        
        for name, script in self.test_scripts.items():
            script_path = Path(__file__).parent / script
            status = "✅" if script_path.exists() else "❌"
            logger.info(f"{status} {name:10} - {script}")
        
        logger.info("=" * 50)
        logger.info("使用方法：")
        logger.info("  python tests/run_tests.py --simple         # 运行简化测试")
        logger.info("  python tests/run_tests.py --quick          # 运行快速测试")
        logger.info("  python tests/run_tests.py --docker         # 运行Docker测试")
        logger.info("  python tests/run_tests.py --full           # 运行完整测试")
        logger.info("  python tests/run_tests.py --comprehensive  # 运行全面API测试")
        logger.info("  python tests/run_tests.py                  # 运行所有测试")
    
    async def run_test_script(self, script_name: str) -> bool:
        """运行单个测试脚本"""
        script_path = Path(__file__).parent / self.test_scripts[script_name]
        
        if not script_path.exists():
            logger.error(f"❌ 测试脚本不存在: {script_path}")
            return False
        
        logger.info(f"🚀 开始运行 {script_name} 测试...")
        logger.info("=" * 60)
        
        try:
            # 导入并运行测试模块
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_module", script_path)
            test_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(test_module)
            
            # 运行main函数
            if hasattr(test_module, 'main'):
                result = await test_module.main()
                return result if result is not None else True
            else:
                logger.warning(f"⚠️ 测试脚本 {script_name} 没有main函数")
                return False
                
        except Exception as e:
            logger.error(f"❌ 运行测试 {script_name} 时出错: {e}")
            return False
    
    async def run_tests(self, test_names: List[str] = None) -> bool:
        """运行指定的测试"""
        if test_names is None:
            test_names = list(self.test_scripts.keys())
        
        logger.info("🔧 数据采集任务管理系统 - 测试运行器")
        logger.info("=" * 60)
        logger.info(f"📊 将运行以下测试: {', '.join(test_names)}")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        for test_name in test_names:
            if test_name not in self.test_scripts:
                logger.warning(f"⚠️ 未知的测试名称: {test_name}")
                continue
            
            test_start = time.time()
            success = await self.run_test_script(test_name)
            test_duration = time.time() - test_start
            
            self.results[test_name] = success
            
            status = "✅ 通过" if success else "❌ 失败"
            logger.info(f"{status} {test_name} 测试 (耗时: {test_duration:.2f}秒)")
            logger.info("-" * 60)
        
        total_duration = time.time() - start_time
        
        # 输出汇总结果
        logger.info("📊 测试结果汇总:")
        logger.info("=" * 60)
        
        passed = sum(1 for result in self.results.values() if result)
        total = len(self.results)
        
        for test_name, success in self.results.items():
            status = "✅ 通过" if success else "❌ 失败"
            logger.info(f"{status} {test_name:10} 测试")
        
        logger.info("-" * 60)
        logger.info(f"总计: {passed}/{total} 测试通过 (耗时: {total_duration:.2f}秒)")
        
        if passed == total:
            logger.success("🎉 所有测试通过！系统运行正常！")
            return True
        else:
            logger.warning(f"⚠️ {total - passed} 个测试失败")
            return False
    
    async def check_prerequisites(self) -> bool:
        """检查运行测试的前置条件"""
        logger.info("🔍 检查测试前置条件...")
        
        # 检查服务器是否运行
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:8000/api/v1/")
                if response.status_code == 200:
                    logger.success("✅ 服务器运行正常")
                else:
                    logger.error(f"❌ 服务器响应异常: {response.status_code}")
                    return False
                
        except Exception as e:
            logger.error(f"❌ 检查服务器状态失败: {e}")
            return False
        
        # 检查依赖包
        required_packages = ["httpx", "loguru"]
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                logger.success(f"✅ {package} 已安装")
            except ImportError:
                missing_packages.append(package)
                logger.error(f"❌ {package} 未安装")
        
        if missing_packages:
            logger.error(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
            logger.info("请运行: pip install " + " ".join(missing_packages))
            return False
        
        logger.success("✅ 所有前置条件满足")
        return True


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据采集任务管理系统测试运行器")
    parser.add_argument("--simple", action="store_true", help="运行简化测试")
    parser.add_argument("--quick", action="store_true", help="运行快速测试")
    parser.add_argument("--docker", action="store_true", help="运行Docker测试")
    parser.add_argument("--full", action="store_true", help="运行完整测试")
    parser.add_argument("--comprehensive", action="store_true", help="运行全面API测试")
    parser.add_argument("--list", action="store_true", help="列出所有可用测试")
    parser.add_argument("--check", action="store_true", help="检查前置条件")
    parser.add_argument("--skip-check", action="store_true", help="跳过前置条件检查")
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    
    runner = TestRunner()
    
    # 列出测试
    if args.list:
        runner.list_tests()
        return
    
    # 检查前置条件
    if args.check:
        success = await runner.check_prerequisites()
        sys.exit(0 if success else 1)
    
    # 跳过前置条件检查
    if not args.skip_check:
        if not await runner.check_prerequisites():
            logger.error("❌ 前置条件检查失败，请解决上述问题后重试")
            sys.exit(1)
    
    # 确定要运行的测试
    test_names = []
    if args.simple:
        test_names.append("simple")
    if args.quick:
        test_names.append("quick")
    if args.docker:
        test_names.append("docker")
    if args.full:
        test_names.append("full")
    if args.comprehensive:
        test_names.append("comprehensive")
    
    # 如果没有指定任何测试，运行所有测试
    if not test_names:
        test_names = ["simple", "quick", "docker", "full", "comprehensive"]
    
    # 运行测试
    success = await runner.run_tests(test_names)
    
    # 退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
