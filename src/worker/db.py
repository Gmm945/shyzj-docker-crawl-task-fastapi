from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()

# 数据库配置
# 从环境变量获取完整的数据库连接字符串
DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+pymysql://app_user:123456@localhost:3306/data_platform')

# 如果URL包含aiomysql，替换为pymysql（因为worker使用同步连接）
if 'mysql+aiomysql://' in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('mysql+aiomysql://', 'mysql+pymysql://')

logger.debug(f"Worker DATABASE_URL: {DATABASE_URL}")

# 创建同步数据库引擎
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=False
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


@contextmanager
def make_sync_session():
    """创建同步数据库会话的上下文管理器"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()
