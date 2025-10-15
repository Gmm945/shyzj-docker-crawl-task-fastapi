"""用户角色关系相关的 schemas"""
from pydantic import BaseModel
from typing import List
from uuid import UUID


class ChangeRolesRequest(BaseModel):
    """修改用户角色请求"""
    uid: UUID  # 用户ID
    rids: List[UUID]  # 角色ID列表
