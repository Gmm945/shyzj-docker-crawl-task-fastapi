from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count

from ...db_util.core import DBSessionDep
from ..models.user import User
from ..schemas.user import UserPagination, UserCreate, UserUpdate
from ..utils.password import get_password_hash


async def create_user(db: DBSessionDep, user_data: UserCreate) -> User:
    """创建用户"""
    # 检查用户名是否已存在
    existing_user = await get_user_by_username(db, user_data.username)
    if existing_user:
        raise ValueError("用户名已存在")
    
    # 检查邮箱是否已存在
    existing_email = await get_user_by_email(db, user_data.email)
    if existing_email:
        raise ValueError("邮箱已存在")
    
    # 创建用户
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_admin=user_data.is_admin,
        is_active=True,
        is_verified=False
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def get_user_by_id(db: DBSessionDep, user_id: UUID) -> Optional[User]:
    """根据ID获取用户"""
    statement = select(User).where(and_(User.id == str(user_id), User.is_delete == False))
    result = await db.execute(statement)
    return result.scalars().first()


async def get_user_by_username(db: DBSessionDep, username: str) -> Optional[User]:
    """根据用户名获取用户"""
    statement = select(User).where(and_(User.username == username, User.is_delete == False))
    result = await db.execute(statement)
    return result.scalars().first()


async def get_user_by_email(db: DBSessionDep, email: str) -> Optional[User]:
    """根据邮箱获取用户"""
    statement = select(User).where(and_(User.email == email, User.is_delete == False))
    result = await db.execute(statement)
    return result.scalars().first()


async def get_all_users(db: DBSessionDep) -> List[User]:
    """获取所有用户"""
    statement = select(User).where(User.is_delete == False)
    result = await db.execute(statement)
    return result.scalars().all()


async def get_page_users(db: DBSessionDep, sort_bys: List[str], sort_orders: List[str], pagination: UserPagination) -> List[User]:
    """分页获取用户列表"""
    stmt = select(User).where(User.is_delete == False)
    
    # 搜索条件
    if pagination.key_word:
        stmt = stmt.where(User.username.contains(pagination.key_word))
    if pagination.is_active is not None:
        stmt = stmt.where(User.is_active == pagination.is_active)
    
    # 排序
    if sort_bys:
        stmt = stmt.order_by(*[getattr(User, sort_field).asc() if sort_order == "asc" 
                              else getattr(User, sort_field).desc()
                              for sort_field, sort_order in zip(sort_bys, sort_orders)])
    
    # 分页（将页码从1开始转换为从0开始）
    offset = (pagination.page - 1) * pagination.page_size
    stmt = stmt.offset(offset).limit(pagination.page_size)
    items = await db.execute(stmt)
    return items.scalars().all()


async def get_page_total(db: DBSessionDep, pagination: UserPagination) -> int:
    """获取分页总数"""
    total_stmt = select(count(User.id)).where(User.is_delete == False)
    if pagination.key_word:
        total_stmt = total_stmt.where(User.username.contains(pagination.key_word))
    if pagination.is_active is not None:
        total_stmt = total_stmt.where(User.is_active == pagination.is_active)
    total = await db.execute(total_stmt)
    return total.scalars().first() or 0


async def update_user_by_id(db: DBSessionDep, user_id: UUID, update_data: dict) -> bool:
    """更新用户"""
    stmt = update(User).where(and_(User.id == user_id, User.is_delete == False)).values(**update_data)
    await db.execute(stmt)
    await db.commit()
    return True


async def delete_user_by_id(db: DBSessionDep, user_id: UUID) -> bool:
    """软删除用户"""
    stmt = update(User).where(User.id == user_id).values({User.is_delete: True})
    await db.execute(stmt)
    await db.commit()
    return True


async def toggle_user_active(db: DBSessionDep, user_id: UUID) -> Optional[bool]:
    """切换用户激活状态"""
    user = await get_user_by_id(db, user_id)
    if user:
        new_status = not user.is_active
        stmt = update(User).where(User.id == user_id).values({User.is_active: new_status})
        await db.execute(stmt)
        await db.commit()
        return new_status
    return None


async def get_active_users_count(db: DBSessionDep) -> int:
    """获取活跃用户数量"""
    statement = select(count(User.id)).where(and_(User.is_active == True, User.is_delete == False))
    result = await db.execute(statement)
    return result.scalars().first() or 0
