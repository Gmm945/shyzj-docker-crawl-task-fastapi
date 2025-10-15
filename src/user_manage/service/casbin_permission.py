"""Casbin 权限管理服务 - 参照 aks-management 实现"""
from typing import List
from sqlalchemy import delete, select, and_, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ...db_util.db import get_casbin_e
from ..models.casbin import CasbinRule, CasbinPermission


# ==================== CasbinRule 核心服务 ====================
async def get_casbin_rules_by_ptype_p_v0(db: AsyncSession, role_key: str):
    """
    根据角色 key 获取所有策略规则 (ptype='p')
    返回该角色拥有的所有资源-动作权限
    """
    statement = select(CasbinRule).where(
        and_(CasbinRule.ptype == "p", CasbinRule.v0 == role_key)
    )
    result = await db.execute(statement)
    return result.scalars().all()


async def get_casbin_rules_by_ptype_g_v1(db: AsyncSession, role_key: str):
    """
    根据角色 key 获取所有组规则 (ptype='g')
    返回所有被分配到该角色的用户
    """
    statement = select(CasbinRule).where(
        and_(CasbinRule.ptype == "g", CasbinRule.v1 == role_key)
    )
    result = await db.execute(statement)
    return result.scalars().all()


async def delete_casbin_rules_by_role_key(db: AsyncSession, role_key: str):
    """
    删除指定角色的所有规则
    包括策略规则(p)和组规则(g)
    """
    try:
        crs = await get_casbin_rules_by_ptype_p_v0(db, role_key)
        if len(crs) > 0:
            stmt_del = delete(CasbinRule).where(
                and_(CasbinRule.ptype == "p", CasbinRule.v0 == role_key)
            )
            result_del = await db.execute(stmt_del)
            deleted_count = result_del.rowcount
            await db.commit()
            logger.info(f"Deleted {deleted_count} CasbinRule rows for role {role_key}")
            return deleted_count
        return 0
    except Exception as e:
        logger.error(f"删除角色规则失败: {e}")
        await db.rollback()
        return 0


async def create_casbin_rules(db: AsyncSession, rules: List[CasbinRule]):
    """
    批量创建 Casbin 规则
    不检查重复，直接添加
    """
    try:
        db.add_all(rules)
        await db.commit()
        return True
    except Exception as e:
        logger.error(f"创建 Casbin 规则失败: {e}")
        await db.rollback()
        return False


async def create_casbin_rule(db: AsyncSession, cr: CasbinRule):
    """
    创建单个 Casbin 规则
    如果相同规则已存在，则不添加
    """
    stmt = select(CasbinRule).where(
        and_(
            CasbinRule.ptype == cr.ptype,
            CasbinRule.v0 == cr.v0,
            CasbinRule.v1 == cr.v1,
            CasbinRule.v2 == cr.v2
        )
    )
    result = await db.execute(stmt)
    exists = result.scalars().first() is not None
    
    if not exists:
        db.add(cr)
        await db.commit()
        return True
    return False


async def delete_casbin_rules_by_ids(db: AsyncSession, rule_ids: List[int]):
    """根据ID批量删除规则"""
    if not rule_ids or len(rule_ids) == 0:
        return 0
    
    try:
        stmt = delete(CasbinRule).where(CasbinRule.id.in_(rule_ids))
        result = await db.execute(stmt)
        deleted_count = result.rowcount
        await db.commit()
        logger.info(f"Deleted {deleted_count} CasbinRule rows")
        return deleted_count
    except Exception as e:
        logger.error(f"删除规则失败: {e}")
        await db.rollback()
        return 0


async def get_casbin_rules_by_obj_key(db: AsyncSession, obj_key: str):
    """根据对象 key 获取所有规则"""
    statement = select(CasbinRule).where(CasbinRule.v1 == obj_key)
    result = await db.execute(statement)
    return result.scalars().all()


async def get_casbin_rules_by_act_key(db: AsyncSession, act_key: str):
    """根据动作 key 获取所有规则"""
    statement = select(CasbinRule).where(CasbinRule.v2 == act_key)
    result = await db.execute(statement)
    return result.scalars().all()


async def get_permission_details_from_rules(db: AsyncSession, rules: List[dict]):
    """
    从规则中获取权限详情
    根据 object_key 和 action_key 查询完整的权限信息
    """
    # 提取所有 (object_key, action_key) 的元组集合
    key_pairs = {(rule['v1'], rule['v2']) for rule in rules if 'v1' in rule and 'v2' in rule}
    
    if not key_pairs:
        return []
    
    # 构造 SQL 查询
    stmt = select(CasbinPermission).where(
        tuple_(CasbinPermission.object_key, CasbinPermission.action_key).in_(key_pairs)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def change_role_casbinrules(db: AsyncSession, role_key: str, crs: List[CasbinRule]):
    """
    修改角色的权限规则
    删除该角色的所有原有权限，然后添加新权限
    """
    try:
        await delete_casbin_rules_by_role_key(db, role_key)
        await create_casbin_rules(db, crs)
        return True
    except Exception as e:
        logger.error(f"修改角色权限规则失败: {e}")
        return False
