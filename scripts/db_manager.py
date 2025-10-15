#!/usr/bin/env python3
"""
统一数据库管理工具 - 基于SQLAlchemy ORM
"""

import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.data_platform_api.models.base import BaseModel
from src.data_platform_api.models.task import Task, TaskExecution, TaskSchedule
from src.user_manage.models.user import User
from src.user_manage.models.casbin import CasbinRule, CasbinObject, CasbinAction, CasbinPermission
from src.user_manage.models.role import Role, MidUserRole

class DatabaseManager:
    def __init__(self):
        self.project_root = project_root
        
        # 从环境变量获取数据库配置
        mysql_host = os.getenv('DATABASE_HOST')
        mysql_port = os.getenv('DATABASE_PORT')
        mysql_user = os.getenv('DATABASE_USER')
        mysql_password = os.getenv('DATABASE_PASSWORD')
        mysql_database = os.getenv('DATABASE_DB_NAME')
        
        # 创建数据库连接URL（不指定数据库，因为数据库可能不存在）
        self.database_url = f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}"
        self.database_name = mysql_database
        
        # 初始化时创建不带数据库的引擎
        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # 创建带数据库的引擎（用于表操作）
        self.database_url_with_db = f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}"
        self.db_engine = None
        
        print(f"🗄️  数据库管理工具 (SQLAlchemy ORM)")
        print(f"📊 数据库: {mysql_database}")
        print(f"🔗 连接: {mysql_host}:{mysql_port}")
        print("=" * 50)

    def _check_connection(self) -> bool:
        """检查数据库连接"""
        print("🔍 检查数据库连接...")
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ 数据库连接成功")
            return True
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            print("请检查.env文件中的数据库配置")
            return False
    
    def _get_db_engine(self):
        """获取带数据库的引擎"""
        if self.db_engine is None:
            self.db_engine = create_engine(self.database_url_with_db, echo=False)
        return self.db_engine

    def _create_database_if_not_exists(self):
        """创建数据库（如果不存在）"""
        try:
            with self.engine.connect() as conn:
                # 检查数据库是否存在
                result = conn.execute(text(f"SHOW DATABASES LIKE '{self.database_name}'"))
                if not result.fetchone():
                    print(f"📝 创建数据库: {self.database_name}")
                    conn.execute(text(f"CREATE DATABASE {self.database_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                    conn.commit()
                    print(f"✅ 数据库创建成功: {self.database_name}")
                else:
                    print(f"ℹ️  数据库已存在: {self.database_name}")
        except Exception as e:
            print(f"❌ 创建数据库失败: {e}")
            raise

    def init_database(self) -> bool:
        """使用SQLAlchemy初始化数据库"""
        print("💾 初始化数据库...")
        
        try:
            # 检查连接
            if not self._check_connection():
                return False
            
            # 创建数据库（如果不存在）
            self._create_database_if_not_exists()
            
            # 导入SQLAlchemy模型
            print("📝 创建表结构...")
            # 使用SQLAlchemy创建所有表
            db_engine = self._get_db_engine()
            BaseModel.metadata.create_all(db_engine)
            print("✅ 表创建完成")
            
            print("\n💡 提示: 使用以下命令初始化权限数据:")
            print("   pdm run db:init_perm")
            
            return True
                    
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            return False

    def reset_database(self) -> bool:
        """重置数据库"""
        print("🔄 重置数据库...")
        
        response = input("⚠️  这将删除所有数据，确定继续？(y/N): ").lower().strip()
        if response not in ['y', 'yes']:
            print("❌ 操作已取消")
            return False
        
        try:
            if not self._check_connection():
                return False
            
            # 删除并重新创建数据库
            print("🗑️  删除数据库...")
            with self.engine.connect() as conn:
                conn.execute(text(f"DROP DATABASE IF EXISTS {self.database_name}"))
                conn.commit()
            
            # 重新创建数据库
            self._create_database_if_not_exists()
            
            print("✅ 数据库重置完成")
            
            # 重新初始化
            return self.init_database()
            
        except Exception as e:
            print(f"❌ 重置数据库失败: {e}")
            return False

    def show_status(self) -> bool:
        """显示数据库状态"""
        print("📊 数据库状态...")
        
        try:
            if not self._check_connection():
                return False
            
            db_engine = self._get_db_engine()
            with db_engine.connect() as conn:
                # 显示所有表
                result = conn.execute(text("SHOW TABLES"))
                tables = [row[0] for row in result]
                print(f"📋 数据库表: {tables}")
                
                # 显示每个表的结构
                for table_name in tables:
                    print(f"\n📋 {table_name} 表结构:")
                    result = conn.execute(text(f"DESCRIBE {table_name}"))
                    for row in result:
                        comment = row[5] if len(row) > 5 and row[5] else 'No comment'
                        print(f"  - {row[0]} ({row[1]}) - {comment}")
                
                # 显示版本信息
                print(f"\n📋 数据库版本: SQLAlchemy ORM版")
                print(f"📋 表创建方式: SQLAlchemy create_all()")
                print(f"📋 字段支持: 基于模型定义自动创建")
            
        except Exception as e:
            print(f"❌ 获取状态失败: {e}")
            return False
        
        return True

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='统一数据库管理工具 (SQLAlchemy ORM)')
    parser.add_argument('action', nargs='?', choices=['init', 'reset', 'status'], 
                       help='操作类型')
    
    args = parser.parse_args()
    
    # 如果没有提供参数，显示帮助信息
    if not args.action:
        parser.print_help()
        print("\n📋 使用示例:")
        print("  python scripts/db_manager.py init     # 初始化数据库")
        print("  python scripts/db_manager.py reset    # 重置数据库")
        print("  python scripts/db_manager.py status   # 查看状态")
        print("\n💡 提示:")
        print("  - 数据库结构变更请使用: pdm run db:reset")
        print("  - 权限数据初始化请使用: pdm run db:init_perm")
        return 1
    
    db_manager = DatabaseManager()
    
    if args.action == 'init':
        if db_manager.init_database():
            print("\n🎉 初始化完成！")
        else:
            print("\n❌ 初始化失败！")
            return 1
    
    elif args.action == 'reset':
        if db_manager.reset_database():
            print("\n✅ 重置完成！")
        else:
            print("\n❌ 重置失败！")
            return 1
    
    elif args.action == 'status':
        if not db_manager.show_status():
            print("\n❌ 获取状态失败！")
            return 1
    
    print("\n📋 下一步:")
    print("  pdm run start            # 启动API服务器")
    print("  pdm run worker    # 启动Celery Worker")
    print("  pdm run beat      # 启动Celery Beat")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())