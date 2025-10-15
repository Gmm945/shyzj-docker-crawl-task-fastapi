import traceback
from typing import List
from uuid import UUID
from loguru import logger
from sqlalchemy import delete, func, insert, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count
from ..schemas.role import RolePagination, RoleCreate
from ..models.user import User
from ..models.role import Role, MidUserRole


async def get_role_count(db: AsyncSession):
    """获取角色总数"""
    statement = select(func.count()).select_from(Role)
    result = await db.execute(statement)
    return result.scalars().first()


async def create_role(db: AsyncSession, role: Role):
    """创建角色"""
    try:
        db.add(role)
        await db.commit()
        await db.refresh(role)
        return role
    except Exception as e:
        logger.error(traceback.format_exc())
        return False


async def get_role_by_role_key(db: AsyncSession, role_key: str):
    """根据 role_key 获取角色"""
    stmt = select(Role).where(Role.role_key == role_key)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_roles(db: AsyncSession, sort_bys: List[str], sort_orders: List[str], role_pn: RolePagination):
    """获取角色列表（包含用户数量统计）"""
    user_count_subq = (
        select(MidUserRole.rid, func.count(MidUserRole.uid).label("raw_user_count"))
        .group_by(MidUserRole.rid)
        .subquery()
    )
    
    stmt = select(
        Role.id,
        Role.name,
        Role.role_key,
        Role.description,
        func.coalesce(user_count_subq.c.raw_user_count, 0).label("user_count"),
        Role.create_time,
        Role.update_time
    ).outerjoin(
        user_count_subq, Role.id == user_count_subq.c.rid
    )
    
    # 搜索条件
    if role_pn.key_word:
        stmt = stmt.where(Role.name.contains(role_pn.key_word))
    
    # 排序
    if sort_bys:
        stmt = stmt.order_by(*[
            getattr(Role, sort_field).asc() if sort_order == "asc"
            else getattr(Role, sort_field).desc()
            for sort_field, sort_order in zip(sort_bys, sort_orders)
        ])
    
    # 分页
    stmt = stmt.offset(role_pn.page * role_pn.page_size).limit(role_pn.page_size)
    items = await db.execute(stmt)
    return items.fetchall()


async def get_page_total(db: AsyncSession, role_pn: RolePagination):
    """获取角色总数"""
    total_stmt = select(count(Role.id))
    if role_pn.key_word:
        total_stmt = total_stmt.where(Role.name.contains(role_pn.key_word))
    total = await db.execute(total_stmt)
    return total.scalars().first()


async def get_roles_by_uid(db: AsyncSession, user_id: UUID):
    """根据用户ID获取用户的所有角色"""
    stmt = select(Role).join(MidUserRole, Role.id == MidUserRole.rid).where(MidUserRole.uid == user_id)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_bind_uids_by_role_id(db: AsyncSession, role_id: UUID):
    """获取绑定到该角色的所有用户ID"""
    statement = select(MidUserRole).where(MidUserRole.rid == role_id)
    result = await db.execute(statement)
    return result.scalars().all()


async def bind_user_role(db: AsyncSession, user_id: UUID, role_id: UUID):
    """绑定用户和角色"""
    stmt_check = select(MidUserRole).where(
        and_(MidUserRole.uid == user_id, MidUserRole.rid == role_id)
    )
    res_check = await db.execute(stmt_check)
    bind_data = res_check.scalars().first()
    
    if bind_data:
        return True
    
    mid_user_role = MidUserRole(uid=user_id, rid=role_id)
    try:
        db.add(mid_user_role)
        await db.commit()
        await db.refresh(mid_user_role)
        return True
    except Exception as e:
        logger.error(traceback.format_exc())
        return False


async def unbind_user_roles_by_uid(db: AsyncSession, user_id: UUID):
    """解绑用户的所有角色"""
    stmt_check = select(MidUserRole).where(MidUserRole.uid == user_id)
    res_check = await db.execute(stmt_check)
    bind_data = res_check.scalars().all()
    
    if len(bind_data) > 0:
        stmt_del = delete(MidUserRole).where(MidUserRole.uid == user_id)
        result_del = await db.execute(stmt_del)
        deleted_count = result_del.rowcount
        await db.commit()
        logger.info(f"Deleted MidUserRole {deleted_count} rows.")
    else:
        logger.info("No bind role")
    return True


async def change_user_roles(db: AsyncSession, user_id: UUID, role_ids: List[UUID]):
    """修改用户的角色"""
    try:
        statement = select(User).where(User.id == user_id)
        result = await db.execute(statement)
        user = result.scalars().first()
        
        if user:
            # 解绑现有角色
            unbind_status = await unbind_user_roles_by_uid(db, str(user_id))
            if unbind_status:
                # 绑定新角色
                m_users = [{'uid': str(user_id), 'rid': str(rid)} for rid in role_ids]
                if m_users:
                    stmt_add = insert(MidUserRole).values(m_users)
                    await db.execute(stmt_add)
                    await db.commit()
        return True
    except Exception:
        logger.error(traceback.format_exc())
        return False
