from uuid import UUID
from fastapi import Query
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from ...common.schemas.base import PaginationModel


class UserBase(BaseModel):
    """用户基础模型"""
    username: str
    email: EmailStr


class UserCreate(BaseModel):
    """用户创建请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, description="密码")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    is_admin: bool = Field(False, description="是否为管理员")


class UserUpdate(BaseModel):
    """用户更新请求"""
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    is_active: Optional[bool] = Field(None, description="是否激活")
    is_admin: Optional[bool] = Field(None, description="是否为管理员")


class UserResponse(BaseModel):
    """用户响应"""
    id: UUID
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    is_verified: bool
    create_time: datetime
    update_time: datetime

    model_config = {
        "from_attributes": True,
        "json_encoders": {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat(),
        }
    }


class UserPagination(PaginationModel):
    """用户分页查询"""
    is_active: Optional[bool] = None
    username: Optional[str] = Field(None, description="用户名模糊搜索")


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordChange(BaseModel):
    """密码修改请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码")
    confirm_password: Optional[str] = Field(None, description="确认密码")


class Token(BaseModel):
    """令牌响应（兼容旧版本）"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    user_id: UUID
    new_password: str
