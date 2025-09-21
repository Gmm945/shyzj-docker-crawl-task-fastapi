from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional

from ...db_util.core import DBSessionDep
from ...common.schemas.base import ResponseModel
from ..schemas.user import UserLogin, TokenResponse, PasswordChange
from ..service.auth import login_user, get_current_user, change_password
from ..service.user import get_user_by_id
from ..models.user import User
from ...config.auth_config import settings

router = APIRouter()
_obj = 'Auth'

# 根据认证开关决定是否启用 OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token") if settings.ENABLE_AUTH else None


async def get_current_active_user(
    db: DBSessionDep,
    token: str = Depends(oauth2_scheme) if settings.ENABLE_AUTH else None
) -> User:
    """获取当前活跃用户"""
    # 如果认证被禁用，返回一个默认的管理员用户
    if not settings.ENABLE_AUTH:
        # 尝试从数据库获取admin用户，如果不存在则创建虚拟用户
        try:
            from ..service.user import get_user_by_username
            admin_user = await get_user_by_username(db, "admin")
            if admin_user:
                return admin_user
        except Exception:
            pass
        
        # 如果数据库中没有admin用户，创建一个虚拟的管理员用户对象
        from uuid import UUID
        from datetime import datetime
        
        class MockUser:
            def __init__(self):
                # 使用固定的UUID，避免每次调用都生成新的
                self.id = UUID("00000000-0000-0000-0000-000000000001")
                self.username = "admin"
                self.email = "admin@example.com"
                self.full_name = "Administrator"
                self.is_active = True
                self.is_admin = True
                self.is_verified = True
                self.create_time = datetime.now()
                self.update_time = datetime.now()
        
        return MockUser()
    
    # 正常认证流程
    user = await get_current_user(db, token)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账户已被禁用"
        )
    return user


@router.post("/login")
async def login(
    login_data: UserLogin,
    db: DBSessionDep
):
    """
    用户登录

    **参数:**
    - `login_data`: 包含用户名和密码的登录信息

    **返回:**
    - 包含访问令牌的JSON响应
    """
    try:
        token_response = await login_user(db, login_data)
        res = ResponseModel(message="登录成功", data=token_response)
        return Response(content=res.model_dump_json())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/token")
async def login_for_access_token(
    db: DBSessionDep,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    使用OAuth2密码流获取访问令牌

    **参数:**
    - `form_data`: OAuth2密码请求表单

    **返回:**
    - 包含访问令牌的JSON响应
    """
    login_data = UserLogin(username=form_data.username, password=form_data.password)
    try:
        token_response = await login_user(db, login_data)
        return token_response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me")
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    获取当前用户信息

    **返回:**
    - 当前用户的详细信息
    """
    res = ResponseModel(message="获取用户信息成功", data={
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "is_verified": current_user.is_verified,
        "create_time": current_user.create_time,
        "update_time": current_user.update_time
    })
    return Response(content=res.model_dump_json())


@router.post("/change-password")
async def change_user_password(
    password_data: PasswordChange,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """
    修改用户密码

    **参数:**
    - `password_data`: 包含旧密码和新密码的修改信息

    **返回:**
    - 修改成功的响应
    """
    await change_password(db, current_user, password_data)
    res = ResponseModel(message="密码修改成功")
    return Response(content=res.model_dump_json())


@router.post("/logout")
async def logout():
    """
    用户登出

    **返回:**
    - 登出成功的响应
    """
    res = ResponseModel(message="登出成功")
    return Response(content=res.model_dump_json())
