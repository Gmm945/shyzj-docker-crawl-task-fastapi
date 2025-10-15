from fastapi import APIRouter, status, Depends
from fastapi.responses import Response
from sqlalchemy.sql import text
from loguru import logger

from ...db_util.core import DBSessionDep
from ...db_util.db import sessionmanager
from ...common.schemas.base import ResponseModel
from ...user_manage.models.user import User
from ...user_manage.service.security import check_permissions
from ..service.common import health_check, get_system_stats

router = APIRouter()
obj = 'Common'  # 资源对象名称


@router.get("/health")
async def health_check_endpoint():
    """简单的健康检查端点"""
    result = await health_check()
    res = ResponseModel(message="系统状态正常", data=result)
    return Response(content=res.model_dump_json(), media_type="application/json")


@router.get("/health/liveness")
async def liveness_check():
    """
    Kubernetes 存活检查端点
    检查应用程序是否正常运行
    如果此检查失败，Kubernetes 将重启容器
    """
    result = await health_check()
    res = ResponseModel(message="服务存活", data=result)
    return Response(content=res.model_dump_json(), media_type="application/json")


@router.get("/health/readiness")
async def readiness_check():
    """
    Kubernetes 就绪检查端点
    检查应用程序是否准备好接受流量
    如果此检查失败，Kubernetes 将不会向此 Pod 转发流量
    """
    # 就绪检查，验证关键依赖（数据库）是否可用
    health_status = {
        "status": "UP",
        "components": {
            "database": {"status": "UNKNOWN"}
        }
    }
    
    # 检查数据库连接
    try:
        async with sessionmanager._engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            if result.scalar() == 1:
                health_status["components"]["database"]["status"] = "UP"
            else:
                health_status["components"]["database"]["status"] = "DOWN"
                health_status["status"] = "DOWN"
    except Exception as e:
        health_status["components"]["database"]["status"] = "DOWN"
        health_status["components"]["database"]["error"] = str(e)
        health_status["status"] = "DOWN"
        logger.error(f"Readiness DB check failed: {e}")

    code = status.HTTP_200_OK if health_status["status"] == "UP" else status.HTTP_503_SERVICE_UNAVAILABLE
    res = ResponseModel(message="就绪检查", data=health_status)
    return Response(content=res.model_dump_json(), media_type="application/json", status_code=code)


@router.get("/stats")
async def get_system_stats_endpoint(
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """获取系统统计信息"""
    stats = await get_system_stats(db)
    res = ResponseModel(message="获取系统统计成功", data=stats)
    return Response(content=res.model_dump_json())