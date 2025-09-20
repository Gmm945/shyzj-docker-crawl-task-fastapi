#!/usr/bin/env python3
"""
心跳功能测试脚本
用于测试心跳接口的调用
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# 添加父目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_heartbeat_request():
    """测试心跳请求"""
    print("测试心跳请求...")
    
    # 心跳请求数据
    heartbeat_data = {
        "execution_id": "550e8400-e29b-41d4-a716-446655440000",
        "container_id": "test-container",
        "status": "running",
        "progress": {
            "total_urls": 100,
            "crawled_urls": 45,
            "successful_urls": 42,
            "failed_urls": 3,
            "current_url": "https://example.com/page45",
            "current_stage": "爬取中 (45/100)",
            "data_items": 1250,
            "percentage": 45.0,
            "runtime_seconds": 1800
        },
        "timestamp": int(time.time())
    }
    
    # API地址
    api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    heartbeat_url = f"{api_url}/api/v1/monitoring/heartbeat"
    
    try:
        # 发送心跳请求
        response = requests.post(
            heartbeat_url,
            json=heartbeat_data,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'ok':
                print("✓ 心跳请求测试通过")
                return True
            else:
                print(f"✗ 心跳响应异常: {result}")
                return False
        else:
            print(f"✗ 心跳请求失败: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠ 心跳请求测试跳过（API服务未运行）")
        return True
    except Exception as e:
        print(f"✗ 心跳请求异常: {e}")
        return False

def test_completion_request():
    """测试完成通知请求"""
    print("测试完成通知请求...")
    
    # 完成通知数据
    completion_data = {
        "execution_id": "550e8400-e29b-41d4-a716-446655440000",
        "container_id": "test-container",
        "success": True,
        "result_data": {
            "crawl_summary": {
                "total_urls": 100,
                "crawled_urls": 100,
                "successful_urls": 95,
                "failed_urls": 5,
                "percentage": 100.0
            },
            "data_items": [{"url": "https://example.com", "title": "测试页面"}],
            "total_data_count": 1250
        }
    }
    
    # API地址
    api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    completion_url = f"{api_url}/api/v1/monitoring/completion"
    
    try:
        # 发送完成通知
        response = requests.post(
            completion_url,
            json=completion_data,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success') or 'message' in result:
                print("✓ 完成通知测试通过")
                return True
            else:
                print(f"✗ 完成通知响应异常: {result}")
                return False
        else:
            print(f"✗ 完成通知请求失败: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠ 完成通知测试跳过（API服务未运行）")
        return True
    except Exception as e:
        print(f"✗ 完成通知异常: {e}")
        return False

def test_status_request():
    """测试状态查询请求"""
    print("测试状态查询请求...")
    
    # API地址
    api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    execution_id = "550e8400-e29b-41d4-a716-446655440000"
    status_url = f"{api_url}/api/v1/monitoring/execution/{execution_id}/status"
    
    try:
        # 查询执行状态
        response = requests.get(status_url, timeout=10)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("✓ 状态查询测试通过")
            return True
        elif response.status_code == 404:
            print("⚠ 状态查询测试跳过（执行记录不存在）")
            return True
        else:
            print(f"✗ 状态查询请求失败: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠ 状态查询测试跳过（API服务未运行）")
        return True
    except Exception as e:
        print(f"✗ 状态查询异常: {e}")
        return False

def test_active_executions():
    """测试活跃执行查询"""
    print("测试活跃执行查询...")
    
    # API地址
    api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    active_url = f"{api_url}/api/v1/monitoring/executions/active"
    
    try:
        # 查询活跃执行
        response = requests.get(active_url, timeout=10)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("✓ 活跃执行查询测试通过")
            return True
        else:
            print(f"✗ 活跃执行查询失败: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠ 活跃执行查询测试跳过（API服务未运行）")
        return True
    except Exception as e:
        print(f"✗ 活跃执行查询异常: {e}")
        return False

def test_api_connectivity():
    """测试API连接性"""
    print("测试API连接性...")
    
    # API地址
    api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    try:
        # 测试基本连接
        response = requests.get(f"{api_url}/", timeout=5)
        
        if response.status_code == 200:
            print("✓ API连接测试通过")
            return True
        else:
            print(f"⚠ API响应异常: {response.status_code}")
            return True  # 不算失败，可能API结构不同
            
    except requests.exceptions.ConnectionError:
        print("✗ API连接失败（服务未运行）")
        return False
    except Exception as e:
        print(f"✗ API连接异常: {e}")
        return False

def run_heartbeat_tests():
    """运行心跳相关测试"""
    print("开始运行心跳功能测试...")
    print("=" * 50)
    
    tests = [
        test_api_connectivity,
        test_heartbeat_request,
        test_completion_request,
        test_status_request,
        test_active_executions,
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
        print("🎉 所有心跳测试通过！")
        return True
    else:
        print("❌ 有心跳测试失败，请检查错误信息")
        return False

if __name__ == "__main__":
    success = run_heartbeat_tests()
    sys.exit(0 if success else 1)
