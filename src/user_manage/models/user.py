import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text
from datetime import datetime

from ...db_util.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="ID")
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="密码哈希")
    full_name = Column(String(100), nullable=True, comment="全名")
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_admin = Column(Boolean, default=False, comment="是否管理员")
    is_verified = Column(Boolean, default=False, comment="是否已验证")
    last_login = Column(DateTime, nullable=True, comment="最后登录时间")
    description = Column(Text, nullable=True, comment="用户描述")
    is_delete = Column(Boolean, nullable=False, default=False, comment="是否软删除")
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
