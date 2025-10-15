"""安全相关服务 - OAuth2、权限控制、Casbin"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ...db_util.db import get_casbin_e, sessionmanager
from ...db_util.core import DBSessionDep
from ..models.user import User
from .role_service import get_roles_by_uid
from .user import get_user_by_username

# 从 auth 模块导入 JWT 配置（避免重复定义）
from .auth import SECRET_KEY, ALGORITHM

# OAuth2 配置（唯一定义处）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    获取当前用户（从 JWT Token）
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    async with sessionmanager.session() as db:
        user = await get_user_by_username(db, username)
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


credentials_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="403_FORBIDDEN! 权限不足",
    headers={"WWW-Authenticate": "Bearer"},
)


def check_permissions(obj: str = None, ex_rule: str = None):
    """
    权限检查装饰器
    
    Args:
        obj: 资源对象 (如: "task", "user", "role")
        ex_rule: 自定义规则 (如果不指定，则使用 HTTP 方法)
    
    Returns:
        检查函数
    
    Example:
        @router.post("/tasks")
        async def create_task(
            user: User = Depends(check_permissions("task"))
        ):
            # 会检查用户是否有 task:POST 权限
            pass
        
        @router.get("/tasks")
        async def get_tasks(
            user: User = Depends(check_permissions("task", "read"))
        ):
            # 会检查用户是否有 task:read 权限
            pass
    """
    async def check(
        request: Request,
        db: DBSessionDep,  # 这里使用 DBSessionDep 是正确的，因为是依赖注入
        user: User = Depends(get_current_user)
    ):
        # 提取URL后缀（去除基础URL）
        suffix_url = str(request.url).removeprefix(str(request.base_url))
        
        # 白名单路径：这些路径不需要权限检查
        whitelist_paths = [
            'user/me',
            'auth/reset_password',
            'auth/logout',
            'auth/refresh'
        ]
        
        if suffix_url in whitelist_paths:
            return user
        
        # 如果没有指定资源对象，直接返回用户（仅需要认证）
        if obj is None:
            return user
        
        # 获取用户的所有角色
        uid = user.id
        roles = await get_roles_by_uid(db=db, user_id=uid)
        
        if not roles:
            logger.warning(f"User {uid} has no roles assigned")
            raise credentials_exception
        
        # 确定要检查的操作（method）
        if ex_rule:
            method = ex_rule
        else:
            method = request.method
        
        # 批量检查用户的每个角色是否有权限
        batch_e = []
        for role in roles:
            e_tuple = (role.role_key, obj, method)
            batch_e.append(e_tuple)
        
        # 批量验证权限
        e = await get_casbin_e()
        ve = e.batch_enforce(batch_e)  # batch_enforce 返回 list，不是 awaitable
        has_permission = sum(ve)  # 只要有一个角色有权限就通过
        
        logger.debug(f"User {uid} permission check for {obj}:{method} = {has_permission > 0}")
        
        if has_permission != 0:
            return user
        else:
            logger.warning(f"User {uid} has no permission for {obj}:{method}")
            raise credentials_exception
    
    return check


async def check_user_permission(user: User, db: AsyncSession, obj: str, action: str) -> bool:
    """
    检查用户是否有指定权限（不抛出异常）
    
    Args:
        user: 用户对象
        db: 数据库会话
        obj: 资源对象
        action: 操作
    
    Returns:
        bool: 是否有权限
    
    Example:
        has_perm = await check_user_permission(user, db, "task", "create")
        if not has_perm:
            return {"error": "权限不足"}
    """
    try:
        # 获取用户的所有角色
        roles = await get_roles_by_uid(db=db, user_id=user.id)
        
        if not roles:
            return False
        
        # 批量检查权限
        batch_e = [(role.role_key, obj, action) for role in roles]
        e = await get_casbin_e()
        ve = e.batch_enforce(batch_e)  # batch_enforce 返回 list
        
        return sum(ve) > 0
    except Exception as e:
        logger.error(f"Error checking permission: {e}")
        return False
