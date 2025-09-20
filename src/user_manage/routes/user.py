from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select

from ...db_util.core import DBSessionDep, CacheManager
from ...common.schemas.base import ResponseModel
from ..schemas.user import UserCreate, UserUpdate, UserResponse, UserPagination
from ..service.user import (
    create_user,
    get_user_by_id,
    get_page_users,
    get_page_total,
    update_user_by_id,
    delete_user_by_id,
    toggle_user_active,
    get_active_users_count
)
from ..routes.auth import get_current_active_user
from ..models.user import User
from ..utils.password import get_password_hash
from ...config.auth_config import settings
# 缓存命名空间常量
user_cache_namespace = 'user'

router = APIRouter()
_obj = 'User'


@router.post("/add")
async def add_user(
    req_body: UserCreate,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """
    创建新用户

    **参数:**
    - `req_body`: 包含用户详情的 `UserCreate` 对象

    **返回:**
    - 包含成功消息和新创建用户ID的JSON响应
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以创建用户"
        )
    
    try:
        new_user = await create_user(db, req_body)
        res = ResponseModel(message="用户创建成功", data={"user_id": new_user.id})
        return Response(content=res.model_dump_json())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/list")
async def get_user_list(
    db: DBSessionDep,
    cache: CacheManager,
    sort_bys: Optional[List[str]] = Query(["create_time"]),
    sort_orders: Optional[List[str]] = Query(["desc"]),
    pagination: UserPagination = Depends(),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取用户列表。支持按激活状态筛选，支持按用户名模糊搜索。

    **参数:**
    - `sort_bys`: 指定排序字段的可选字符串列表。默认为 `["create_time"]`
    - `sort_orders`: 指定每个字段排序顺序的可选字符串列表。默认为 `["desc"]`
    - `pagination`: 包含分页参数和筛选条件的 `UserPagination` 对象

    **返回:**
    - 包含用户列表和分页信息的JSON响应
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以查看用户列表"
        )
    
    # 构建缓存键
    cache_key_parts = [
        str(current_user.id),
        str(pagination.page),
        str(pagination.page_size),
        str(pagination.is_active),
        str(pagination.username),
        ",".join(sort_bys),
        ",".join(sort_orders)
    ]
    
    # 尝试从缓存获取
    cached_result = await cache.get_cache(user_cache_namespace, cache_key_parts)
    if cached_result:
        return Response(content=cached_result)
    
    users = await get_page_users(db, sort_bys, sort_orders, pagination)
    total = await get_page_total(db, pagination)
    
    user_list = [UserResponse.model_validate(user) for user in users]
    
    res = ResponseModel(message="获取用户列表成功", data={
        "items": user_list,
        "total": total,
        "page": pagination.page + 1,
        "size": pagination.page_size,
        "pages": (total + pagination.page_size - 1) // pagination.page_size
    })
    
    result_json = res.model_dump_json()
    
    # 缓存结果（10分钟）
    await cache.set_cache(user_cache_namespace, cache_key_parts, result_json, ttl=600)
    
    return Response(content=result_json)


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取用户详情

    **参数:**
    - `user_id`: 用户ID

    **返回:**
    - 包含用户详情的JSON响应
    """
    # 检查权限：只能查看自己的信息，管理员可以查看所有用户
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能查看自己的用户信息"
        )
    
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    res = ResponseModel(message="获取用户详情成功", data=UserResponse.model_validate(user))
    return Response(content=res.model_dump_json())


@router.put("/{user_id}")
async def update_user(
    user_id: UUID,
    req_body: UserUpdate,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """
    更新用户信息

    **参数:**
    - `user_id`: 用户ID
    - `req_body`: 包含更新信息的 `UserUpdate` 对象

    **返回:**
    - 更新成功的响应
    """
    # 检查权限：只能修改自己的信息，管理员可以修改所有用户
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能修改自己的用户信息"
        )
    
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 非管理员不能修改管理员权限
    if not current_user.is_admin and req_body.is_admin is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能修改管理员权限"
        )
    
    update_data = req_body.model_dump(exclude_unset=True)
    await update_user_by_id(db, user_id, update_data)
    
    res = ResponseModel(message="用户更新成功")
    return Response(content=res.model_dump_json())


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """
    删除用户

    **参数:**
    - `user_id`: 用户ID

    **返回:**
    - 删除成功的响应
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以删除用户"
        )
    
    # 不能删除自己
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己"
        )
    
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    await delete_user_by_id(db, user_id)
    res = ResponseModel(message="用户删除成功")
    return Response(content=res.model_dump_json())


@router.post("/{user_id}/toggle-active")
async def toggle_user_active_status(
    user_id: UUID,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """
    切换用户激活状态

    **参数:**
    - `user_id`: 用户ID

    **返回:**
    - 切换成功的响应
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以切换用户状态"
        )
    
    # 不能切换自己的状态
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能切换自己的状态"
        )
    
    new_status = await toggle_user_active(db, user_id)
    if new_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    status_text = "激活" if new_status else "禁用"
    res = ResponseModel(message=f"用户{status_text}成功", data={"is_active": new_status})
    return Response(content=res.model_dump_json())


@router.get("/stats/active-count")
async def get_active_users_count_endpoint(
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取活跃用户数量

    **返回:**
    - 包含活跃用户数量的JSON响应
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以查看统计信息"
        )
    
    count = await get_active_users_count(db)
    res = ResponseModel(message="获取活跃用户数量成功", data={"active_users_count": count})
    return Response(content=res.model_dump_json())


@router.post("/init-admin", response_model=ResponseModel)
async def init_admin(db: DBSessionDep):
    """初始化管理员账户（仅在没有管理员时可用）"""
    # 检查是否已有管理员
    result = await db.execute(select(User).where(User.is_admin == True))
    existing_admin = result.scalar_one_or_none()
    
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="管理员账户已存在"
        )
    
    # 创建管理员账户
    admin_user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
        is_active=True,
        is_admin=True
    )
    db.add(admin_user)
    await db.commit()
    
    res = ResponseModel(message="管理员账户创建成功", data={"username": "admin"})
    return Response(content=res.model_dump_json())
