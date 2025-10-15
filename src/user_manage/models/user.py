from sqlalchemy import Column, String, Boolean, DateTime, Text
from ...data_platform_api.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    hashed_password = Column(String(1024), nullable=False, comment="密码哈希")
    full_name = Column(String(100), nullable=True, comment="全名")
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_admin = Column(Boolean, default=False, comment="是否管理员")
    is_verified = Column(Boolean, default=False, comment="是否已验证")
    last_login = Column(DateTime, nullable=True, comment="最后登录时间")
    description = Column(Text, nullable=True, comment="用户描述")
