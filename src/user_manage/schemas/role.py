from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import Query


class RoleBase(BaseModel):
    """角色基础模型"""
    name: str
    description: Optional[str] = None


class RoleCreate(BaseModel):
    """创建角色请求"""
    name: str
    role_key: Optional[str] = None  # 可选，会自动生成
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    """更新角色请求"""
    name: Optional[str] = None
    role_key: Optional[str] = None
    description: Optional[str] = None


class RoleModel(BaseModel):
    """角色模型"""
    id: UUID
    name: str
    role_key: str
    description: Optional[str] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class RolePageModel(BaseModel):
    """角色列表模型（包含用户数量）"""
    id: UUID
    name: str
    role_key: str
    user_count: Optional[int] = 0
    description: Optional[str] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None


class RolePagination(BaseModel):
    """角色分页参数"""
    page: int = Query(0, ge=0)
    page_size: int = Query(10, ge=1)
    key_word: Optional[str] = None


class UserRoleAssign(BaseModel):
    """用户角色分配请求"""
    user_id: UUID
    role_ids: List[UUID]


class RolePermissionAssign(BaseModel):
    """角色权限分配请求"""
    permissions: List[str]  # 格式: ["object_key:action_key"]


class RoleWithPermissions(RoleModel):
    """带权限的角色模型"""
    permissions: List[str] = []
