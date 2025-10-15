import uuid
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from ...data_platform_api.models.base import BaseModel
from ...db_util.db import Base


class CasbinObject(BaseModel):
    """Casbin 资源对象模型"""
    __tablename__ = 'casbin_object'
    __table_args__ = {'extend_existing': True}

    name = Column(String(128), nullable=False, comment='资源名称')
    object_key = Column(String(128), nullable=False, unique=True, comment='资源标识')
    description = Column(String(128), nullable=True, comment='资源描述')


class CasbinAction(BaseModel):
    """Casbin 动作模型"""
    __tablename__ = 'casbin_action'
    __table_args__ = {'extend_existing': True}

    name = Column(String(128), nullable=False, comment='动作名称')
    action_key = Column(String(128), nullable=False, unique=True, comment='动作标识')
    description = Column(String(128), nullable=True, comment='动作描述')


class CasbinPermission(BaseModel):
    """Casbin 权限模型"""
    __tablename__ = 'casbin_permission'
    __table_args__ = {'extend_existing': True}

    name = Column(String(128), nullable=False, comment='权限名称')
    type = Column(String(128), nullable=False, comment='权限类型:function/page')
    object_key = Column(String(128), nullable=False, comment='资源标识')
    action_key = Column(String(128), nullable=False, comment='动作标识')
    description = Column(String(128), nullable=True, comment='权限描述')
    module = Column(String(128), nullable=False, default='默认管理', comment='权限模块')


class CasbinRule(Base):
    """Casbin 规则模型 - 直接继承 Base，不使用 BaseModel"""
    __tablename__ = "casbin_rule"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ptype = Column(String(255), comment='策略类型 (p/g)')
    v0 = Column(String(255), comment='主体 (用户/角色)')
    v1 = Column(String(255), comment='资源')
    v2 = Column(String(255), comment='动作')
    v3 = Column(String(255), comment='扩展字段1')
    v4 = Column(String(255), comment='扩展字段2')
    v5 = Column(String(255), comment='扩展字段3')

    def __str__(self):
        arr = [self.ptype]
        for v in (self.v0, self.v1, self.v2, self.v3, self.v4, self.v5):
            if v is None:
                break
            arr.append(v)
        return ", ".join(arr)

    def __repr__(self):
        return '<CasbinRule {}: "{}">'.format(self.id, str(self))
