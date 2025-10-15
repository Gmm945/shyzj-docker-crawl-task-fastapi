import uuid
from sqlalchemy import Column, String, DateTime
from datetime import datetime

from ...data_platform_api.models.base import BaseModel


class Role(BaseModel):
    """角色模型"""
    __tablename__ = "role"
    __table_args__ = {'extend_existing': True}

    name = Column(String(32), nullable=False, comment='角色名称')
    role_key = Column(String(128), nullable=False, unique=True, comment='角色唯一标识')
    description = Column(String(128), nullable=True, comment='角色描述')


class MidUserRole(BaseModel):
    """用户角色关联表"""
    __tablename__ = "mid_user_role"
    __table_args__ = {'extend_existing': True}

    uid = Column(String(36), nullable=False, comment='用户ID')
    rid = Column(String(36), nullable=False, comment='角色ID')
