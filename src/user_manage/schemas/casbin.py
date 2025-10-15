from fastapi import Query
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from enum import Enum
from datetime import datetime


class CasbinPermType(str, Enum):
    """权限类型枚举"""
    FUNCTION = 'function'
    PAGE = 'page'


class CreateCasbinObject(BaseModel):
    """创建 Casbin 对象请求"""
    name: str
    object_key: str
    description: Optional[str] = None


class EditCasbinObject(BaseModel):
    """编辑 Casbin 对象请求"""
    old_co_id: UUID
    name: str
    object_key: str
    description: Optional[str] = None


class CreateCasbinAction(BaseModel):
    """创建 Casbin 动作请求"""
    name: str
    action_key: str
    description: Optional[str] = None


class EditCasbinAction(BaseModel):
    """编辑 Casbin 动作请求"""
    old_ca_id: UUID
    name: str
    action_key: str
    description: Optional[str] = None


class CasbinRule(BaseModel):
    """Casbin 规则"""
    obj: str
    act: str


class AddCasbinPermRequest(BaseModel):
    """添加 Casbin 权限请求"""
    name: str
    object_key: str
    action_key: str
    description: Optional[str] = None
    module: str
    type: CasbinPermType = CasbinPermType.FUNCTION


class BatchAddPermRequest(BaseModel):
    """批量添加权限请求"""
    perm_list: List[AddCasbinPermRequest]


class CasbinPermModel(BaseModel):
    """Casbin 权限模型"""
    id: UUID
    name: str
    type: CasbinPermType
    object_key: str
    action_key: str
    description: Optional[str] = None
    module: str
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None


class PermPagination(BaseModel):
    """权限分页请求"""
    page: int = Query(0, ge=0)
    page_size: int = Query(10, ge=1)
    key_word: Optional[str] = None
    module: Optional[str] = None
    type: Optional[CasbinPermType] = None


class CasbinObjectModel(BaseModel):
    """Casbin 对象模型"""
    id: UUID
    name: str
    object_key: str
    description: Optional[str] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None


class CasbinActionModel(BaseModel):
    """Casbin 动作模型"""
    id: UUID
    name: str
    action_key: str
    description: Optional[str] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None


class PermModel(BaseModel):
    """权限模型"""
    object_key: str  # 资源标识
    action_key: str  # 动作标识
