from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
import sys

from .db_util.db import sessionmanager
from .config.auth_config import settings
from .data_platform_api.main import api_router
from .utils.scheduler import schedule_manager


# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


# Middleware
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时
    logger.info("数据采集任务管理系统启动中...")
    
    try:
        # 暂时禁用任务调度器启动，避免异步循环冲突
        # schedule_manager.start()
        # logger.info("任务调度器启动完成")
        
        logger.info("数据采集任务管理系统启动完成")
        
    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        raise
    
    yield
    
    # 关闭时
    logger.info("数据采集任务管理系统关闭中...")
    try:
        # 暂时禁用任务调度器停止
        # schedule_manager.stop()
        # logger.info("任务调度器已停止")
        
        # 关闭数据库连接
        if sessionmanager._engine is not None:
            await sessionmanager.close()
        
        logger.info("数据采集任务管理系统已关闭")
    except Exception as e:
        logger.error(f"系统关闭异常: {e}")


# 确保origins中的URL使用正确的scheme
origins = [
    "http://localhost:3002",
    "http://localhost:8089",
    settings.APP_CORS,
]
APP_CORS_ALLOW_ORIGINS = settings.APP_CORS_ALLOW_ORIGINS.split(',') if settings.APP_CORS_ALLOW_ORIGINS else []
origins.extend(APP_CORS_ALLOW_ORIGINS)

api_str = "/api/v1"

app = FastAPI(
    title="数据采集任务管理系统",
    description="基于FastAPI、MySQL、Redis、Celery的数据采集任务管理平台",
    version="1.0.0",
    root_path=api_str, 
    lifespan=lifespan, 
    default_response_class=JSONResponse,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CharsetMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # 修改响应头，统一加上 charset=utf-8
        if response.media_type and "charset" not in response.headers.get("content-type", ""):
            response.headers["Content-Type"] = f"{response.media_type}; charset=utf-8"
        return response

app.add_middleware(CharsetMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.APP_SECRET_KEY)

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "message": "服务器内部错误",
            "data": None,
            "detail": str(exc)
        }
    )

# 注册路由 - 参照 AKS 项目的路由注册方式
app.include_router(api_router, tags=["data_platform_api"])

# 根路径
@app.get("/")
async def root():
    return {
        "message": "数据采集任务管理系统",
        "data": {
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

def main():
    """主函数，供PDM脚本调用"""
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8089,
        reload=True,
        log_config=None  # 禁用uvicorn的默认日志配置
    )

if __name__ == "__main__":
    main()
