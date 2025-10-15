"""Casbin 服务层 - 参照 aks-management 实现"""
import os
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_, func
from sqlalchemy.sql.functions import count
from loguru import logger

from ...db_util.db import get_casbin_e
from ..models.casbin import CasbinRule, CasbinObject, CasbinAction, CasbinPermission
from ..models.role import Role, MidUserRole
from ..schemas.casbin import (
    CreateCasbinObject, EditCasbinObject, CreateCasbinAction, EditCasbinAction,
    AddCasbinPermRequest, BatchAddPermRequest, PermPagination, CasbinPermType
)
from ..schemas.role import RoleCreate, RoleUpdate


# ==================== CasbinObject 服务 ====================
async def create_casbin_object(db: AsyncSession, obj_data: CreateCasbinObject) -> CasbinObject:
    """创建 Casbin 对象"""
    db_obj = CasbinObject(
        name=obj_data.name,
        object_key=obj_data.object_key,
        description=obj_data.description
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_casbin_objects(db: AsyncSession) -> List[CasbinObject]:
    """获取所有 Casbin 对象"""
    statement = select(CasbinObject)
    result = await db.execute(statement)
    return result.scalars().all()


async def update_casbin_object(db: AsyncSession, obj_id: str, obj_data: EditCasbinObject) -> bool:
    """更新 Casbin 对象"""
    statement = select(CasbinObject).where(CasbinObject.id == obj_id)
    result = await db.execute(statement)
    obj = result.scalars().first()
    
    if obj:
        obj.name = obj_data.name
        obj.object_key = obj_data.object_key
        obj.description = obj_data.description
        await db.commit()
        return True
    return False


async def delete_casbin_object(db: AsyncSession, obj_id: str) -> bool:
    """删除 Casbin 对象"""
    statement = select(CasbinObject).where(CasbinObject.id == obj_id)
    result = await db.execute(statement)
    obj = result.scalars().first()
    
    if obj:
        await db.delete(obj)
        await db.commit()
        return True
    return False


# ==================== CasbinAction 服务 ====================
async def create_casbin_action(db: AsyncSession, action_data: CreateCasbinAction) -> CasbinAction:
    """创建 Casbin 动作"""
    db_action = CasbinAction(
        name=action_data.name,
        action_key=action_data.action_key,
        description=action_data.description
    )
    db.add(db_action)
    await db.commit()
    await db.refresh(db_action)
    return db_action


async def get_casbin_actions(db: AsyncSession) -> List[CasbinAction]:
    """获取所有 Casbin 动作"""
    statement = select(CasbinAction)
    result = await db.execute(statement)
    return result.scalars().all()


async def update_casbin_action(db: AsyncSession, action_id: str, action_data: EditCasbinAction) -> bool:
    """更新 Casbin 动作"""
    statement = select(CasbinAction).where(CasbinAction.id == action_id)
    result = await db.execute(statement)
    action = result.scalars().first()
    
    if action:
        action.name = action_data.name
        action.action_key = action_data.action_key
        action.description = action_data.description
        await db.commit()
        return True
    return False


async def delete_casbin_action(db: AsyncSession, action_id: str) -> bool:
    """删除 Casbin 动作"""
    statement = select(CasbinAction).where(CasbinAction.id == action_id)
    result = await db.execute(statement)
    action = result.scalars().first()
    
    if action:
        await db.delete(action)
        await db.commit()
        return True
    return False


# ==================== CasbinPermission 服务 ====================
async def create_casbin_permission(db: AsyncSession, perm_data: AddCasbinPermRequest) -> CasbinPermission:
    """创建 Casbin 权限"""
    db_perm = CasbinPermission(
        name=perm_data.name,
        type=perm_data.type.value,
        object_key=perm_data.object_key,
        action_key=perm_data.action_key,
        description=perm_data.description,
        module=perm_data.module
    )
    db.add(db_perm)
    await db.commit()
    await db.refresh(db_perm)
    return db_perm


async def batch_create_casbin_permissions(db: AsyncSession, perm_list: BatchAddPermRequest) -> bool:
    """批量创建 Casbin 权限"""
    try:
        db_perms = []
        for perm_data in perm_list.perm_list:
            db_perm = CasbinPermission(
                name=perm_data.name,
                type=perm_data.type.value,
                object_key=perm_data.object_key,
                action_key=perm_data.action_key,
                description=perm_data.description,
                module=perm_data.module
            )
            db_perms.append(db_perm)
        
        db.add_all(db_perms)
        await db.commit()
        return True
    except Exception as e:
        logger.error(f"批量创建权限失败: {e}")
        return False


async def get_casbin_permissions(db: AsyncSession, pagination: PermPagination) -> List[CasbinPermission]:
    """分页获取 Casbin 权限"""
    stmt = select(CasbinPermission)
    
    # 搜索条件
    if pagination.key_word:
        stmt = stmt.where(CasbinPermission.name.contains(pagination.key_word))
    if pagination.module:
        stmt = stmt.where(CasbinPermission.module == pagination.module)
    if pagination.type:
        stmt = stmt.where(CasbinPermission.type == pagination.type.value)
    
    # 分页
    offset = pagination.page * pagination.page_size
    stmt = stmt.offset(offset).limit(pagination.page_size)
    
    result = await db.execute(stmt)
    return result.scalars().all()


async def count_casbin_permissions(db: AsyncSession, pagination: PermPagination) -> int:
    """获取权限总数"""
    stmt = select(count(CasbinPermission.id))
    
    # 搜索条件
    if pagination.key_word:
        stmt = stmt.where(CasbinPermission.name.contains(pagination.key_word))
    if pagination.module:
        stmt = stmt.where(CasbinPermission.module == pagination.module)
    if pagination.type:
        stmt = stmt.where(CasbinPermission.type == pagination.type.value)
    
    result = await db.execute(stmt)
    return result.scalars().first() or 0


# ==================== Role 服务 ====================
async def create_role(db: AsyncSession, role_data: RoleCreate) -> Role:
    """创建角色"""
    db_role = Role(
        name=role_data.name,
        role_key=role_data.role_key,
        description=role_data.description
    )
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)
    return db_role


async def get_roles(db: AsyncSession) -> List[Role]:
    """获取所有角色"""
    statement = select(Role)
    result = await db.execute(statement)
    return result.scalars().all()


async def get_role_by_id(db: AsyncSession, role_id: str) -> Optional[Role]:
    """根据ID获取角色"""
    statement = select(Role).where(Role.id == role_id)
    result = await db.execute(statement)
    return result.scalars().first()


async def get_role_by_key(db: AsyncSession, role_key: str) -> Optional[Role]:
    """根据角色标识获取角色"""
    statement = select(Role).where(Role.role_key == role_key)
    result = await db.execute(statement)
    return result.scalars().first()


async def update_role(db: AsyncSession, role_id: str, role_data: RoleUpdate) -> bool:
    """更新角色"""
    statement = select(Role).where(Role.id == role_id)
    result = await db.execute(statement)
    role = result.scalars().first()
    
    if role:
        if role_data.name is not None:
            role.name = role_data.name
        if role_data.role_key is not None:
            role.role_key = role_data.role_key
        if role_data.description is not None:
            role.description = role_data.description
        await db.commit()
        return True
    return False


async def delete_role(db: AsyncSession, role_id: str) -> bool:
    """删除角色"""
    statement = select(Role).where(Role.id == role_id)
    result = await db.execute(statement)
    role = result.scalars().first()
    
    if role:
        await db.delete(role)
        await db.commit()
        return True
    return False