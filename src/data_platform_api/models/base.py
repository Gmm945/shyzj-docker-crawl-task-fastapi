import uuid
from sqlalchemy import Boolean, Column, DateTime, String
from datetime import datetime
from ...db_util.db import Base

class BaseModel(Base):
    __abstract__ = True
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="ID")
    is_delete = Column(Boolean, nullable=False, default=False, comment="是否软删除")
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
