from fastapi import APIRouter

from .routes import (
    common,
    tasks,
    monitoring,
    scheduler,
)
from ..user_manage.routes import user, auth, role

api_router = APIRouter()

# 注册路由 - 参照 AKS 项目的路由组织方式
api_router.include_router(common.router, tags=["common"], prefix="/common")

# 用户管理模块
api_router.include_router(auth.router, tags=["user_manage"], prefix="/auth")
api_router.include_router(user.router, tags=["user_manage"], prefix="/user")
api_router.include_router(role.router, tags=["role_manage"], prefix="/role")

# 业务模块
api_router.include_router(tasks.router, tags=["task_manage"], prefix="/task")
api_router.include_router(monitoring.router, tags=["monitoring"], prefix="/monitoring")
api_router.include_router(scheduler.router, tags=["scheduler"], prefix="/scheduler")
