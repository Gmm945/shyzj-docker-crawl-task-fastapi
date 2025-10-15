from typing import List, Optional
from uuid import UUID
import uuid
from fastapi import APIRouter, Depends, Query, Response, status, HTTPException

from ...common.schemas.base import ResponseModel
from ...db_util.core import DBSessionDep
from ..models.user import User
from ..models.role import Role
from ..models.casbin import CasbinRule
from ..service.casbin_service import (
    create_role,
    get_role_by_id,
    update_role,
    delete_role,
)
from ..service.casbin_permission import (
    get_casbin_rules_by_ptype_p_v0,
    delete_casbin_rules_by_role_key,
    create_casbin_rules,
    get_permission_details_from_rules,
)
from ..service.role_service import (
    get_page_total,
    get_bind_uids_by_role_id,
    get_roles_by_uid,
    change_user_roles,
)
from ..service.security import check_permissions
from ..schemas.role import (
    RoleCreate,
    RoleUpdate,
    RoleModel,
    RolePagination,
    RolePageModel,
    RolePermissionAssign,
)
from ..schemas.user_role import ChangeRolesRequest
from ..schemas.casbin import CasbinPermModel, PermModel

router = APIRouter()
obj = 'Role'  # 资源对象名称


@router.post("/add", summary="添加角色")
async def add_role(
    role_body: RoleCreate,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """添加新角色"""
    try:
        # 自动生成 role_key
        role_key = f'role_{uuid.uuid4().hex}'
        
        # 创建角色
        new_role = await create_role(db, RoleCreate(
            name=role_body.name,
            role_key=role_key,
            description=role_body.description
        ))
        
        res = ResponseModel(
            message="添加角色成功",
            data={'role_id': str(new_role.id), 'role_key': new_role.role_key}
        )
        return Response(content=res.model_dump_json())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加角色失败: {str(e)}")


@router.get("/list", summary="获取角色列表")
async def get_role_list(
    db: DBSessionDep,
    sort_bys: Optional[List[str]] = Query(["create_time"]),
    sort_orders: Optional[List[str]] = Query(["desc"]),
    pagination: RolePagination = Depends(),
    user: User = Depends(check_permissions(obj))
):
    """获取角色列表（带分页）"""
    try:
        from ..service.role_service import get_roles as get_roles_with_count
        
        roles_data = await get_roles_with_count(db, sort_bys, sort_orders, pagination)
        total_data = await get_page_total(db, pagination)
        
        roles = [RolePageModel(
            id=r.id,
            name=r.name,
            role_key=r.role_key,
            user_count=r.user_count if hasattr(r, 'user_count') else 0,
            description=r.description,
            create_time=r.create_time,
            update_time=r.update_time
        ).model_dump() for r in roles_data]
        
        res = ResponseModel(
            message="获取角色列表成功",
            data={"total": total_data, "roles": roles}
        )
        return Response(content=res.model_dump_json())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取角色列表失败: {str(e)}")


@router.get("/{role_id}", summary="获取角色详情")
async def get_role_by_role_id(
    role_id: UUID,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """根据ID获取角色详情"""
    role = await get_role_by_id(db, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    role_model = RoleModel.model_validate(role, from_attributes=True).model_dump()
    res = ResponseModel(message="获取角色成功", data=role_model)
    return Response(content=res.model_dump_json())


@router.put("/{role_id}", summary="更新角色")
async def update_role_by_id(
    role_id: UUID,
    role_body: RoleUpdate,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """更新角色信息"""
    role = await get_role_by_id(db, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 检查是否是系统默认角色
    if hasattr(role, 'role_key') and role.role_key in ['role_sysadmin', 'role_admin']:
        res = ResponseModel(message="无法修改系统默认角色", data={})
        return Response(content=res.model_dump_json(), status_code=status.HTTP_400_BAD_REQUEST)
    
    success = await update_role(db, str(role_id), role_body)
    if success:
        res = ResponseModel(message="更新角色成功", data={})
        return Response(content=res.model_dump_json())
    else:
        raise HTTPException(status_code=500, detail="更新角色失败")


@router.delete("/{role_id}", summary="删除角色")
async def delete_role_by_role_id(
    role_id: UUID,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """删除角色"""
    role = await get_role_by_id(db, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 检查是否是系统默认角色
    if hasattr(role, 'role_key') and role.role_key in ['role_sysadmin', 'role_admin']:
        res = ResponseModel(message="无法删除系统默认角色", data={})
        return Response(content=res.model_dump_json(), status_code=status.HTTP_400_BAD_REQUEST)
    
    # 检查是否有用户绑定
    has_bind_uids = await get_bind_uids_by_role_id(db, role_id)
    if len(has_bind_uids) > 0:
        res = ResponseModel(message="删除失败，请先解绑所有用户", data={})
        return Response(content=res.model_dump_json(), status_code=status.HTTP_409_CONFLICT)
    
    success = await delete_role(db, str(role_id))
    if success:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    else:
        raise HTTPException(status_code=500, detail="删除角色失败")


@router.put("/{role_id}/save_perms", summary="保存角色权限")
async def save_role_perms(
    role_id: UUID,
    role_body: RolePermissionAssign,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """保存角色的权限配置"""
    role = await get_role_by_id(db, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 检查是否是系统管理员角色
    if hasattr(role, 'role_key') and role.role_key == 'role_sysadmin':
        res = ResponseModel(message="无法修改系统管理员权限", data={})
        return Response(content=res.model_dump_json(), status_code=status.HTTP_400_BAD_REQUEST)
    
    try:
        # 删除现有权限
        await delete_casbin_rules_by_role_key(db, role.role_key)
        
        # 添加新权限
        cas_rules = [
            CasbinRule(
                ptype='p',
                v0=role.role_key,
                v1=perm.split(':')[0],
                v2=perm.split(':')[1]
            ) for perm in role_body.permissions if ':' in perm
        ]
        
        if cas_rules:
            await create_casbin_rules(db, cas_rules)
        
        await db.commit()
        
        res = ResponseModel(message="保存角色权限成功", data={})
        return Response(content=res.model_dump_json())
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"保存角色权限失败: {str(e)}")


@router.get("/{role_id}/perms", summary="获取角色权限")
async def get_role_perms(
    role_id: UUID,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """获取角色的所有权限"""
    role = await get_role_by_id(db, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    try:
        # 获取角色的 casbin 规则
        rules_data = await get_casbin_rules_by_ptype_p_v0(db, role.role_key)
        rules = [
            {'v0': rule.v0, 'v1': rule.v1, 'v2': rule.v2}
            for rule in rules_data if rule.v1 and rule.v2
        ]
        
        # 获取权限详情
        bound_perms_data = await get_permission_details_from_rules(db, rules)
        bound_perms = [
            CasbinPermModel.model_validate(c, from_attributes=True).model_dump()
            for c in bound_perms_data
        ]
        
        res = ResponseModel(
            message="获取角色权限成功",
            data={"bound_perms": bound_perms}
        )
        return Response(content=res.model_dump_json())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取角色权限失败: {str(e)}")


@router.put("/change_user_roles", summary="修改用户角色")
async def set_user_role(
    body: ChangeRolesRequest,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """修改用户的角色"""
    try:
        await change_user_roles(db, body.uid, body.rids)
        res = ResponseModel(message="修改用户角色成功", data={})
        return Response(content=res.model_dump_json())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改用户角色失败: {str(e)}")


@router.get("/get_roles_by_uid/{user_id}", summary="获取用户的所有角色")
async def get_user_role_by_user_id(
    user_id: UUID,
    db: DBSessionDep,
    user: User = Depends(check_permissions(obj))
):
    """根据用户ID获取该用户的所有角色"""
    try:
        roles = await get_roles_by_uid(db, user_id)
        roles_data = [
            RoleModel.model_validate(r, from_attributes=True).model_dump()
            for r in roles
        ]
        
        res = ResponseModel(
            message="获取用户角色成功",
            data={'uid': str(user_id), 'roles': roles_data}
        )
        return Response(content=res.model_dump_json())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户角色失败: {str(e)}")
