#!/usr/bin/env python3
"""
Docker任务诊断脚本
================

检查Docker任务容器的启动和运行状态，发现潜在问题

使用方法：
    python tests/diagnose_docker_task.py
"""

import subprocess
import json
import os
from loguru import logger

def run_command(cmd):
    """执行shell命令"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True,
            timeout=10
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

def check_docker_available():
    """检查Docker是否可用"""
    logger.info("🔍 检查Docker服务...")
    stdout, stderr, code = run_command("docker ps")
    if code == 0:
        logger.success("✅ Docker服务正常运行")
        return True
    else:
        logger.error(f"❌ Docker服务异常: {stderr}")
        return False

def get_task_containers():
    """获取所有任务容器"""
    logger.info("📦 查找任务容器...")
    cmd = 'docker ps -a --filter "name=task-" --format "{{.Names}}"'
    stdout, stderr, code = run_command(cmd)
    
    if code != 0:
        logger.error(f"❌ 获取容器列表失败: {stderr}")
        return []
    
    containers = [name.strip() for name in stdout.split('\n') if name.strip()]
    logger.info(f"找到 {len(containers)} 个任务容器")
    return containers

def inspect_container(container_name):
    """详细检查容器"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🔎 检查容器: {container_name}")
    logger.info(f"{'='*60}")
    
    # 获取容器详细信息
    cmd = f'docker inspect {container_name}'
    stdout, stderr, code = run_command(cmd)
    
    if code != 0:
        logger.error(f"❌ 获取容器信息失败: {stderr}")
        return
    
    try:
        container_info = json.loads(stdout)[0]
        
        # 1. 容器状态
        state = container_info['State']
        logger.info(f"📊 容器状态:")
        logger.info(f"  - Status: {state['Status']}")
        logger.info(f"  - Running: {state['Running']}")
        logger.info(f"  - ExitCode: {state['ExitCode']}")
        
        if state.get('Error'):
            logger.error(f"  - ❌ 错误: {state['Error']}")
        
        # 2. 环境变量
        config = container_info['Config']
        logger.info(f"\n🔧 环境配置:")
        logger.info(f"  - 镜像: {config['Image']}")
        logger.info(f"  - 命令: {' '.join(config['Cmd'])}")
        
        env_dict = {}
        for env in config['Env']:
            if '=' in env:
                key, value = env.split('=', 1)
                if key in ['TASK_EXECUTION_ID', 'CONFIG_PATH', 'API_BASE_URL']:
                    env_dict[key] = value
        
        for key, value in env_dict.items():
            logger.info(f"  - {key}: {value}")
        
        # 检查API_BASE_URL
        api_url = env_dict.get('API_BASE_URL', '')
        if '8000' in api_url:
            logger.warning(f"  ⚠️ API_BASE_URL可能有误: {api_url}")
            logger.warning(f"     应该是: http://localhost:8089")
        
        # 3. 端口映射
        network_settings = container_info['NetworkSettings']
        ports = network_settings.get('Ports', {})
        logger.info(f"\n🌐 端口映射:")
        if ports:
            for container_port, host_bindings in ports.items():
                if host_bindings:
                    for binding in host_bindings:
                        host_port = binding['HostPort']
                        logger.info(f"  - {container_port} -> {host_port}")
                        
                        # 检查端口是否被占用
                        check_cmd = f"lsof -i :{host_port} | grep LISTEN"
                        stdout, _, _ = run_command(check_cmd)
                        if stdout:
                            logger.warning(f"    ⚠️ 端口 {host_port} 可能被占用:")
                            for line in stdout.split('\n')[:3]:
                                if line.strip():
                                    logger.warning(f"       {line}")
        else:
            logger.info("  - 无端口映射")
        
        # 4. 挂载点
        mounts = container_info['Mounts']
        logger.info(f"\n📁 挂载点:")
        for mount in mounts:
            source = mount['Source']
            dest = mount['Destination']
            logger.info(f"  - {source} -> {dest}")
            
            # 检查配置文件是否存在
            if 'config.json' in dest:
                if os.path.exists(source):
                    size = os.path.getsize(source)
                    logger.success(f"    ✅ 配置文件存在 ({size} bytes)")
                    
                    # 读取配置内容
                    try:
                        with open(source, 'r') as f:
                            config_data = json.load(f)
                            logger.info(f"    📄 配置内容预览:")
                            logger.info(f"       任务名称: {config_data.get('task_name', 'N/A')}")
                            logger.info(f"       任务类型: {config_data.get('task_type', 'N/A')}")
                            logger.info(f"       基础URL: {config_data.get('base_url', 'N/A')}")
                    except Exception as e:
                        logger.warning(f"    ⚠️ 无法读取配置: {e}")
                else:
                    logger.error(f"    ❌ 配置文件不存在!")
        
        # 5. 容器日志
        logger.info(f"\n📜 容器日志:")
        log_cmd = f"docker logs {container_name} 2>&1 | tail -20"
        log_stdout, _, _ = run_command(log_cmd)
        
        if log_stdout.strip():
            logger.info("  最后20行:")
            for line in log_stdout.split('\n'):
                if line.strip():
                    if 'error' in line.lower() or 'exception' in line.lower():
                        logger.error(f"    {line}")
                    else:
                        logger.info(f"    {line}")
        else:
            logger.warning("  ⚠️ 容器日志为空（容器可能未启动）")
        
    except Exception as e:
        logger.error(f"❌ 解析容器信息失败: {e}")

def check_port_usage():
    """检查常用端口占用"""
    logger.info(f"\n{'='*60}")
    logger.info("🔌 检查端口占用情况")
    logger.info(f"{'='*60}")
    
    # 检查50000-50100范围的端口
    logger.info("检查端口范围 50000-50010...")
    for port in range(50000, 50011):
        cmd = f"lsof -i :{port} -sTCP:LISTEN -t 2>/dev/null"
        stdout, _, _ = run_command(cmd)
        if stdout.strip():
            logger.warning(f"  ⚠️ 端口 {port} 被占用")
        else:
            logger.info(f"  ✅ 端口 {port} 可用")

def check_api_service():
    """检查API服务"""
    logger.info(f"\n{'='*60}")
    logger.info("🌐 检查API服务")
    logger.info(f"{'='*60}")
    
    import requests
    
    for port in [8000, 8089]:
        try:
            response = requests.get(f"http://localhost:{port}/api/v1/", timeout=2)
            if response.status_code == 200:
                logger.success(f"✅ 端口 {port}: API服务正常运行")
            else:
                logger.warning(f"⚠️ 端口 {port}: HTTP {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.info(f"  ℹ️ 端口 {port}: 无服务运行")
        except Exception as e:
            logger.warning(f"  ⚠️ 端口 {port}: {e}")

def main():
    """主函数"""
    logger.info("🚀 开始Docker任务诊断")
    logger.info("="*60)
    
    # 1. 检查Docker
    if not check_docker_available():
        return
    
    # 2. 检查API服务
    check_api_service()
    
    # 3. 检查端口占用
    check_port_usage()
    
    # 4. 获取并检查所有任务容器
    containers = get_task_containers()
    
    if not containers:
        logger.warning("⚠️ 没有找到任务容器")
        logger.info("\n💡 建议:")
        logger.info("  1. 创建一个测试任务")
        logger.info("  2. 触发任务执行")
        logger.info("  3. 然后再运行此诊断脚本")
        return
    
    # 检查每个容器
    for container in containers[:5]:  # 只检查前5个
        inspect_container(container)
    
    # 总结
    logger.info(f"\n{'='*60}")
    logger.info("📊 诊断总结")
    logger.info(f"{'='*60}")
    logger.info(f"✅ 检查了 {min(len(containers), 5)} 个容器")
    logger.info("\n💡 常见问题和解决方案:")
    logger.info("  1. 端口被占用 -> 清理旧容器或使用不同端口")
    logger.info("  2. API_BASE_URL错误 -> 检查配置，应该是 localhost:8089")
    logger.info("  3. 配置文件不存在 -> 检查任务配置是否正确")
    logger.info("  4. 容器未启动 -> 检查Docker日志和系统资源")

if __name__ == "__main__":
    main()

