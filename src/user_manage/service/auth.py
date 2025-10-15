"""认证相关服务 - 登录、密码、Token 生成"""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.auth_config import settings
from ..models.user import User
from ..schemas.user import UserLogin, TokenResponse, PasswordChange
from ..utils.password import verify_password, get_password_hash
from .user import get_user_by_username, get_user_by_email, update_user_by_id

# JWT 配置（唯一定义处）
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """验证用户凭据"""
    # 尝试通过用户名查找
    user = await get_user_by_username(db, username)
    
    # 如果用户名没找到，尝试通过邮箱查找
    if not user:
        user = await get_user_by_email(db, username)
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


async def login_user(db: AsyncSession, login_data: UserLogin) -> TokenResponse:
    """用户登录"""
    user = await authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账户已被禁用"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


async def change_password(db: AsyncSession, user: User, password_data: PasswordChange) -> bool:
    """修改密码"""
    if not verify_password(password_data.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    new_hashed_password = get_password_hash(password_data.new_password)
    await update_user_by_id(db, user.id, {"hashed_password": new_hashed_password})
    
    return True
