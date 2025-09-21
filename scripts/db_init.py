#!/usr/bin/env python3
"""数据库初始化脚本"""

import subprocess
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent

def run_command(cmd, description, check=True):
    """运行命令并输出结果"""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=check, cwd=project_root)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ {description}失败: {e}")
        return False

def check_pdm_project():
    """检查PDM项目是否已初始化"""
    if not (project_root / "pdm.lock").exists():
        print("📦 PDM项目未初始化，正在初始化...")
        return run_command("pdm install", "安装依赖")
    return True

def check_alembic_config():
    """检查Alembic配置"""
    if not (project_root / "alembic.ini").exists():
        print("❌ 找不到alembic.ini文件")
        return False
    return True

def check_db_connection():
    """检查数据库连接"""
    print("🔍 检查数据库连接...")
    test_code = """
from src.db_util.db import sessionmanager
from src.config.auth_config import settings
from sqlalchemy import text
try:
    import asyncio
    async def test_connection():
        async with sessionmanager.session() as db:
            result = await db.execute(text('SELECT VERSION()'))
            version = result.fetchone()[0]
            print(f'✅ 数据库连接成功，MySQL版本: {version}')
        return True
    asyncio.run(test_connection())
    exit(0)
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
    print(f'数据库URL: {settings.DATABASE_URL}')
    exit(1)
"""
    try:
        result = subprocess.run([sys.executable, "-c", test_code], cwd=project_root)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 数据库连接检查失败: {e}")
        return False

def check_migration_files():
    """检查是否需要创建迁移文件"""
    versions_dir = project_root / "alembic" / "versions"
    if not versions_dir.exists():
        return True
    
    # 检查是否有迁移文件（排除__pycache__和__init__.py）
    migration_files = [
        f for f in versions_dir.iterdir() 
        if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"
    ]
    
    return len(migration_files) == 0

def create_admin_user():
    """创建管理员用户"""
    response = input("是否创建管理员账户？(y/N): ").lower().strip()
    if response not in ['y', 'yes']:
        return
    
    print("👤 创建管理员账户...")
    admin_code = """
import requests
import sys
from src.config.auth_config import settings

try:
    response = requests.post('http://localhost:8000/api/v1/user/init-admin')
    if response.status_code == 200:
        print('✅ 管理员账户创建成功！')
        print(f'👤 用户名: admin')
        print(f'🔑 密码: {settings.ADMIN_PASSWORD}')
    else:
        print(f'❌ 创建管理员账户失败: {response.text}')
except Exception as e:
    print(f'⚠️  请确保Web服务已启动，然后手动访问 http://localhost:8000/api/v1/user/init-admin')
    print(f'错误: {e}')
"""
    subprocess.run([sys.executable, "-c", admin_code], cwd=project_root)

def main():
    """数据库初始化主函数"""
    print("💾 初始化数据库（使用PDM）...")
    
    # 检查PDM项目
    if not check_pdm_project():
        return 1
    
    # 检查Alembic配置
    if not check_alembic_config():
        return 1
    
    # 检查数据库连接
    if not check_db_connection():
        return 1
    
    # 创建迁移文件（如果需要）
    if check_migration_files():
        print("📝 创建初始迁移文件...")
        if not run_command("pdm run db-init", "创建迁移文件"):
            print("⚠️  创建迁移文件失败，但继续执行")
    
    # 执行迁移
    print("📋 执行数据库迁移...")
    if not run_command("pdm run db-upgrade", "执行数据库迁移"):
        print("❌ 数据库迁移失败")
        return 1
    
    print("✅ 数据库初始化完成！")
    
    # 询问是否创建管理员账户
    create_admin_user()
    
    print("\n🎉 初始化完成！")
    print("\n📋 下一步:")
    print("  pdm run dev:start       # 启动开发服务器")
    print("  pdm run celery:all      # 启动所有Celery服务")
    print("  pdm run docs            # 查看API文档")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
