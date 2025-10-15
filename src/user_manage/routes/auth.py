from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm

from ...db_util.core import DBSessionDep
from ...common.schemas.base import ResponseModel
from ..schemas.user import UserLogin, PasswordChange
from ..service.auth import login_user, change_password
from ..service.security import get_current_user
from ..models.user import User

router = APIRouter()
_obj = 'Auth'


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账户已被禁用"
        )
    return current_user


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
    用户登出,前端删除token即可,后端无需处理,此接口无实际逻辑

    **返回:**
    - 登出成功的响应
    """
    res = ResponseModel(message="登出成功")
    return Response(content=res.model_dump_json())
