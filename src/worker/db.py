from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger
from ..config.auth_config import settings

# 使用配置中的同步数据库URL
DATABASE_URL = settings.sync_database_url

logger.debug(f"Worker DATABASE_URL: {DATABASE_URL}")

# 创建同步数据库引擎
engine = create_engine(
    DATABASE_URL,
    **settings.worker_database_engine_kwargs
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
