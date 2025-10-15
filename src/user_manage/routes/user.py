from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select

from ...db_util.core import DBSessionDep
from ...common.schemas.base import ResponseModel
from ..schemas.user import UserCreate, UserUpdate, UserResponse, UserPagination, ResetPasswordRequest
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
    
    users = await get_page_users(db, sort_bys, sort_orders, pagination)
    total = await get_page_total(db, pagination)
    
    user_list = [UserResponse.model_validate(user) for user in users]
    
    return ResponseModel(message="获取用户列表成功", data={
        "items": user_list,
        "total": total,
        "page": pagination.page,
        "size": pagination.page_size,
        "pages": (total + pagination.page_size - 1) // pagination.page_size
    })


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


@router.put("/{user_id}/reset-password")
async def admin_reset_user_password(
    user_id: UUID,
    req_body: ResetPasswordRequest,
    db: DBSessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """
    管理员重置用户密码
    
    **参数:**
    - `user_id`: 要重置密码的用户ID
    - `req_body`: 包含新密码的请求体
    
    **返回:**
    - 重置成功的响应
    
    **权限:**
    - 只有管理员可以重置其他用户的密码
    """
    # 检查权限：只有管理员可以重置密码
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以重置用户密码"
        )
    
    # 检查用户是否存在
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 重置密码
    new_hashed_password = get_password_hash(req_body.new_password)
    
    # 直接更新用户对象（使用 ORM 方式）
    user.hashed_password = new_hashed_password
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    res = ResponseModel(
        message="密码重置成功", 
        data={"user_id": str(user_id), "username": user.username}
    )
    return Response(content=res.model_dump_json())
