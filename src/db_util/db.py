import os
import sys
import warnings
import contextlib
from typing import Any, AsyncGenerator, AsyncIterator
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from loguru import logger
import casbin
from casbin_async_sqlalchemy_adapter import Adapter
from ..config.auth_config import settings

warnings.filterwarnings('ignore')

# 使用配置中的异步数据库URL
DATABASE_URL = settings.async_database_url

logger.debug(f"Async DATABASE_URL: {DATABASE_URL}")

# 添加当前目录到系统路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

class Base(DeclarativeBase):
    pass

class DatabaseSessionManager:
    """数据库会话管理器"""

    def __init__(self, host: str, engine_kwargs: dict[str, Any] = {}):
        self._engine = create_async_engine(host, **engine_kwargs)
        self._sessionmaker = async_sessionmaker(autocommit=False, bind=self._engine, expire_on_commit=False)

    async def close(self):
        """关闭数据库连接"""
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        """获取数据库连接"""
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as connection:
            try:
                yield connection
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """获取数据库会话"""
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
            # 在会话结束时，提交事务
            await session.commit()
        except Exception:
            await session.rollback()  # 回滚未提交的事务
            raise
        finally:
            await session.close()  # 确保关闭会话，释放资源

# 创建数据库会话管理器
sessionmanager = DatabaseSessionManager(DATABASE_URL, settings.database_engine_kwargs)

# 创建 Casbin Adapter
adapter = Adapter(sessionmanager._engine)

async def get_casbin_e():
    """
    获取 Casbin Enforcer
    每次调用都创建新的 enforcer 并加载策略（参照 aks-management 实现）
    """
    # 加载 casbin 模型配置文件
    model_path = os.path.join(BASE_DIR, 'rbac_model.conf')
    enforcer = casbin.AsyncEnforcer(model_path, adapter)
    await enforcer.load_policy()
    return enforcer

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话的依赖注入函数"""
    async with sessionmanager.session() as session:
        yield session
