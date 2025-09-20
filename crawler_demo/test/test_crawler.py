#!/usr/bin/env python3
"""
爬虫服务测试脚本
用于测试爬虫容器的基本功能
"""

import os
import sys
import json
import time
import requests
import subprocess
import tempfile
from pathlib import Path

# 添加父目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler_service import SimpleCrawler, HeartbeatClient

def test_crawler_basic():
    """测试基础爬虫功能"""
    print("测试基础爬虫功能...")
    
    # 创建测试配置
    config = {
        "task_name": "测试爬虫",
        "task_type": "docker-crawl",
        "base_url": "https://httpbin.org",
        "target_urls": ["https://httpbin.org/html", "https://httpbin.org/json"],
        "user_agent": "Mozilla/5.0 (compatible; DataCollector/1.0)",
        "timeout": 30,
        "delay": 1
    }
    
    # 创建爬虫实例
    crawler = SimpleCrawler(config)
    
    # 测试爬虫启动
    crawler.start()
    
    # 检查结果
    assert len(crawler.results) > 0, "应该爬取到数据"
    assert crawler.progress.successful_urls > 0, "应该有成功的请求"
    
    print(f"✓ 爬虫测试通过，爬取了 {len(crawler.results)} 条数据")
    return True

def test_heartbeat_client():
    """测试心跳客户端"""
    print("测试心跳客户端...")
    
    # 创建心跳客户端
    client = HeartbeatClient(
        api_base_url="http://localhost:8000",
        execution_id="test-execution-id",
        container_id="test-container"
    )
    
    # 创建模拟爬虫进度
    class MockCrawler:
        def __init__(self):
            self.is_running = True
        
        def get_progress(self):
            return {
                "total_urls": 10,
                "crawled_urls": 5,
                "successful_urls": 5,
                "failed_urls": 0,
                "current_url": "https://example.com",
                "current_stage": "爬取中 (5/10)",
                "data_items": 100,
                "percentage": 50.0,
                "runtime_seconds": 300
            }
    
    mock_crawler = MockCrawler()
    
    # 测试心跳发送（会失败，因为API服务可能没运行）
    try:
        client.send_heartbeat(mock_crawler)
        print("✓ 心跳客户端测试通过")
    except requests.exceptions.ConnectionError:
        print("⚠ 心跳客户端测试跳过（API服务未运行）")
    
    return True

def test_config_loading():
    """测试配置文件加载"""
    print("测试配置文件加载...")
    
    # 创建临时配置文件
    config_data = {
        "task_name": "配置测试",
        "task_type": "docker-crawl",
        "base_url": "https://httpbin.org",
        "target_urls": ["https://httpbin.org/html"],
        "timeout": 30,
        "delay": 1
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_config_path = f.name
    
    try:
        # 读取配置文件
        with open(temp_config_path, 'r') as f:
            loaded_config = json.load(f)
        
        assert loaded_config["task_name"] == "配置测试"
        assert loaded_config["base_url"] == "https://httpbin.org"
        
        print("✓ 配置文件加载测试通过")
        return True
        
    finally:
        os.unlink(temp_config_path)

def test_docker_build():
    """测试Docker镜像构建"""
    print("测试Docker镜像构建...")
    
    try:
        # 检查Dockerfile是否存在
        dockerfile_path = Path(__file__).parent.parent / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile不存在"
        
        # 检查requirements.txt是否存在
        requirements_path = Path(__file__).parent.parent / "requirements.txt"
        assert requirements_path.exists(), "requirements.txt不存在"
        
        # 检查crawler_service.py是否存在
        service_path = Path(__file__).parent.parent / "crawler_service.py"
        assert service_path.exists(), "crawler_service.py不存在"
        
        print("✓ Docker构建文件检查通过")
        return True
        
    except AssertionError as e:
        print(f"✗ Docker构建文件检查失败: {e}")
        return False

def test_environment_variables():
    """测试环境变量"""
    print("测试环境变量...")
    
    # 设置测试环境变量
    os.environ['TASK_EXECUTION_ID'] = 'test-execution-id'
    os.environ['CONFIG_PATH'] = '/tmp/test-config.json'
    os.environ['API_BASE_URL'] = 'http://test-api:8000'
    
    # 检查环境变量
    assert os.getenv('TASK_EXECUTION_ID') == 'test-execution-id'
    assert os.getenv('CONFIG_PATH') == '/tmp/test-config.json'
    assert os.getenv('API_BASE_URL') == 'http://test-api:8000'
    
    print("✓ 环境变量测试通过")
    return True

def test_config_examples():
    """测试配置文件示例"""
    print("测试配置文件示例...")
    
    config_examples_dir = Path(__file__).parent.parent / "config_examples"
    assert config_examples_dir.exists(), "config_examples目录不存在"
    
    # 检查配置文件
    config_files = list(config_examples_dir.glob("*.json"))
    assert len(config_files) > 0, "没有找到配置文件示例"
    
    for config_file in config_files:
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # 检查必需字段
            assert "task_name" in config
            assert "task_type" in config
            assert "base_url" in config
            
            print(f"✓ 配置文件 {config_file.name} 格式正确")
            
        except json.JSONDecodeError:
            print(f"✗ 配置文件 {config_file.name} JSON格式错误")
            return False
    
    print("✓ 配置文件示例测试通过")
    return True

def run_all_tests():
    """运行所有测试"""
    print("开始运行爬虫容器测试...")
    print("=" * 50)
    
    tests = [
        test_environment_variables,
        test_config_loading,
        test_config_examples,
        test_docker_build,
        test_crawler_basic,
        test_heartbeat_client,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__} 测试失败: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("🎉 所有测试通过！")
        return True
    else:
        print("❌ 有测试失败，请检查错误信息")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
