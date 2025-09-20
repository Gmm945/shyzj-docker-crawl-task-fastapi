from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger

from ...db_util.db import sessionmanager
from .task import get_running_tasks_count
from ...user_manage.service.user import get_active_users_count


async def health_check():
    """健康检查"""
    return {"status": "ok", "message": "Service is running"}


async def database_health_check():
    """数据库健康检查"""
    try:
        async with sessionmanager._engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            if result.scalar() == 1:
                return {"status": "UP", "message": "Database connection is healthy"}
            else:
                return {"status": "DOWN", "message": "Database query failed"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "DOWN", "message": f"Database connection failed: {str(e)}"}


async def get_system_stats(db: AsyncSession):
    """获取系统统计信息"""
    try:
        running_tasks = await get_running_tasks_count(db)
        active_users = await get_active_users_count(db)
        
        return {
            "running_tasks": running_tasks,
            "active_users": active_users,
            "status": "ok"
        }
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        return {
            "running_tasks": 0,
            "active_users": 0,
            "status": "error",
            "error": str(e)
        }
