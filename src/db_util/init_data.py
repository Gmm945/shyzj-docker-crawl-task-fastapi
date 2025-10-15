#!/usr/bin/env python3
"""
初始化数据脚本 - 参照 aks-management 实现
创建默认角色、用户、权限规则
"""

import contextlib
import asyncio
import os
import sys

# 添加项目根路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(project_root)

from sqlalchemy import select
from .db import get_async_session
from ..user_manage.models.user import User
from ..user_manage.models.role import Role
from ..user_manage.models.casbin import CasbinAction, CasbinObject, CasbinRule, CasbinPermission
from ..user_manage.utils.password import get_password_hash
from ..user_manage.service.role_service import (
    get_role_count,
    create_role,
    get_roles_by_uid,
    get_role_by_role_key,
    bind_user_role,
)
from ..user_manage.service.casbin_permission import (
    delete_casbin_rules_by_role_key,
    create_casbin_rules,
)

get_async_session_context = contextlib.asynccontextmanager(get_async_session)


async def create_data():
    """初始化数据"""
    async with get_async_session_context() as db:
        print("🚀 开始初始化数据...")
        
        # ==================== 1. 创建基础角色 ====================
        if await get_role_count(db) == 0:
            print("📝 创建基础角色...")
            # 系统管理员角色
            r1 = await create_role(db, Role(
                name='系统管理员',
                role_key='role_sysadmin',
                description='系统管理员，拥有所有系统权限'
            ))
            # 任务管理员角色
            r2 = await create_role(db, Role(
                name='任务管理员',
                role_key='role_task_manager',
                description='可以管理任务和调度'
            ))
            # 普通用户角色
            r3 = await create_role(db, Role(
                name='普通用户',
                role_key='role_user',
                description='只能查看和执行任务'
            ))
            print("✅ 角色创建完成")
        
        # ==================== 2. 创建 CasbinAction ====================
        # 检查是否已存在
        stmt = select(CasbinAction)
        result = await db.execute(stmt)
        existing_actions = result.scalars().all()
        
        if len(existing_actions) == 0:
            print("📝 创建 Casbin Actions...")
            cas = [
                CasbinAction(name='创建/新增', action_key='POST', description='创建资源'),
                CasbinAction(name='获取/查询', action_key='GET', description='获取资源'),
                CasbinAction(name='更新/修改', action_key='PUT', description='更新资源'),
                CasbinAction(name='部分更新', action_key='PATCH', description='部分更新资源'),
                CasbinAction(name='删除', action_key='DELETE', description='删除资源'),
                CasbinAction(name='执行', action_key='EXECUTE', description='执行操作'),
                CasbinAction(name='停止', action_key='STOP', description='停止操作'),
            ]
            db.add_all(cas)
            await db.commit()
            print("✅ CasbinAction 创建完成")
        
        # ==================== 3. 创建 CasbinObject ====================
        stmt = select(CasbinObject)
        result = await db.execute(stmt)
        existing_objects = result.scalars().all()
        
        if len(existing_objects) == 0:
            print("📝 创建 Casbin Objects...")
            cos = [
                # 用户管理相关
                CasbinObject(name='用户', object_key='User', description='用户资源'),
                CasbinObject(name='角色', object_key='Role', description='角色资源'),
                CasbinObject(name='权限', object_key='Perm', description='权限资源'),
                CasbinObject(name='Casbin对象', object_key='CasbinObject', description='Casbin对象资源'),
                CasbinObject(name='Casbin动作', object_key='CasbinAction', description='Casbin动作资源'),
                CasbinObject(name='Casbin规则', object_key='CasbinRule', description='Casbin规则资源'),
                
                # 业务资源
                CasbinObject(name='任务', object_key='Task', description='数据采集任务资源'),
                CasbinObject(name='调度', object_key='Scheduler', description='任务调度资源'),
                CasbinObject(name='监控', object_key='Monitoring', description='系统监控资源'),
                CasbinObject(name='公共资源', object_key='Common', description='公共资源'),
            ]
            db.add_all(cos)
            await db.commit()
            print("✅ CasbinObject 创建完成")
        
        # ==================== 4. 创建 CasbinPermission ====================
        stmt = select(CasbinPermission)
        result = await db.execute(stmt)
        existing_perms = result.scalars().all()
        
        if len(existing_perms) == 0:
            print("📝 创建 Casbin Permissions...")
            perms = [
                # 用户管理
                CasbinPermission(name='创建用户', object_key='User', action_key='POST', type='function', module='用户管理', description='创建新用户'),
                CasbinPermission(name='获取用户信息', object_key='User', action_key='GET', type='function', module='用户管理', description='获取用户信息'),
                CasbinPermission(name='更新用户信息', object_key='User', action_key='PUT', type='function', module='用户管理', description='更新用户信息'),
                CasbinPermission(name='部分更新用户', object_key='User', action_key='PATCH', type='function', module='用户管理', description='部分更新用户'),
                CasbinPermission(name='删除用户', object_key='User', action_key='DELETE', type='function', module='用户管理', description='删除用户'),
                
                # 角色管理
                CasbinPermission(name='创建角色', object_key='Role', action_key='POST', type='function', module='用户管理', description='创建新角色'),
                CasbinPermission(name='获取角色信息', object_key='Role', action_key='GET', type='function', module='用户管理', description='获取角色信息'),
                CasbinPermission(name='更新角色', object_key='Role', action_key='PUT', type='function', module='用户管理', description='更新角色'),
                CasbinPermission(name='删除角色', object_key='Role', action_key='DELETE', type='function', module='用户管理', description='删除角色'),
                
                # 任务管理
                CasbinPermission(name='创建任务', object_key='Task', action_key='POST', type='function', module='任务管理', description='创建数据采集任务'),
                CasbinPermission(name='获取任务信息', object_key='Task', action_key='GET', type='function', module='任务管理', description='获取任务信息'),
                CasbinPermission(name='更新任务', object_key='Task', action_key='PUT', type='function', module='任务管理', description='更新任务配置'),
                CasbinPermission(name='删除任务', object_key='Task', action_key='DELETE', type='function', module='任务管理', description='删除任务'),
                CasbinPermission(name='执行任务', object_key='Task', action_key='EXECUTE', type='function', module='任务管理', description='立即执行任务'),
                CasbinPermission(name='停止任务', object_key='Task', action_key='STOP', type='function', module='任务管理', description='停止正在执行的任务'),
                
                # 调度管理
                CasbinPermission(name='创建调度', object_key='Scheduler', action_key='POST', type='function', module='调度管理', description='创建任务调度'),
                CasbinPermission(name='获取调度信息', object_key='Scheduler', action_key='GET', type='function', module='调度管理', description='获取调度信息'),
                CasbinPermission(name='更新调度', object_key='Scheduler', action_key='PUT', type='function', module='调度管理', description='更新调度配置'),
                CasbinPermission(name='删除调度', object_key='Scheduler', action_key='DELETE', type='function', module='调度管理', description='删除调度'),
                
                # 监控管理
                CasbinPermission(name='获取监控信息', object_key='Monitoring', action_key='GET', type='function', module='监控管理', description='获取系统监控信息'),
                CasbinPermission(name='检查超时', object_key='Monitoring', action_key='POST', type='function', module='监控管理', description='检查心跳超时'),
                
                # 公共资源
                CasbinPermission(name='获取公共资源', object_key='Common', action_key='GET', type='function', module='公共资源', description='获取公共资源和健康检查'),
            ]
            db.add_all(perms)
            await db.commit()
            print("✅ CasbinPermission 创建完成")
        
        # ==================== 5. 初始化角色权限规则 ====================
        print("📝 初始化角色权限规则...")
        
        # 删除现有规则
        del_admin_cnt = await delete_casbin_rules_by_role_key(db, 'role_sysadmin')
        del_manager_cnt = await delete_casbin_rules_by_role_key(db, 'role_task_manager')
        del_user_cnt = await delete_casbin_rules_by_role_key(db, 'role_user')
        
        print(f"  清理旧规则: sysadmin({del_admin_cnt}), task_manager({del_manager_cnt}), user({del_user_cnt})")
        
        # HTTP 方法
        acts = ['POST', 'GET', 'PUT', 'DELETE', 'PATCH']
        task_acts = ['POST', 'GET', 'PUT', 'DELETE', 'EXECUTE', 'STOP']
        
        # 系统管理员对象（拥有所有权限）
        admin_objs = [
            'User', 'Role', 'Perm', 'CasbinObject', 'CasbinAction', 'CasbinRule',
            'Task', 'Scheduler', 'Monitoring', 'Common'
        ]
        
        # 任务管理员对象（任务和调度相关权限）
        task_manager_objs = ['Task', 'Scheduler', 'Monitoring', 'Common']
        
        # 普通用户对象（只读和执行权限）
        user_objs = ['Task', 'Common']
        user_read_acts = ['GET']
        user_exec_acts = ['EXECUTE']
        
        # 创建规则列表
        crs = []
        
        # 系统管理员：所有资源的所有权限
        for obj in admin_objs:
            if obj == 'Task':
                for act in task_acts:
                    crs.append(CasbinRule(ptype='p', v0='role_sysadmin', v1=obj, v2=act))
            else:
                for act in acts:
                    crs.append(CasbinRule(ptype='p', v0='role_sysadmin', v1=obj, v2=act))
        
        # 任务管理员：任务和调度的所有权限
        for obj in task_manager_objs:
            if obj == 'Task':
                for act in task_acts:
                    crs.append(CasbinRule(ptype='p', v0='role_task_manager', v1=obj, v2=act))
            elif obj in ['Scheduler', 'Monitoring']:
                for act in acts:
                    crs.append(CasbinRule(ptype='p', v0='role_task_manager', v1=obj, v2=act))
            elif obj == 'Common':
                crs.append(CasbinRule(ptype='p', v0='role_task_manager', v1=obj, v2='GET'))
        
        # 普通用户：只能查看和执行任务
        for obj in user_objs:
            if obj == 'Task':
                # 查看权限
                for act in user_read_acts:
                    crs.append(CasbinRule(ptype='p', v0='role_user', v1=obj, v2=act))
                # 执行权限
                for act in user_exec_acts:
                    crs.append(CasbinRule(ptype='p', v0='role_user', v1=obj, v2=act))
            elif obj == 'Common':
                crs.append(CasbinRule(ptype='p', v0='role_user', v1=obj, v2='GET'))
        
        # 添加规则到数据库
        await create_casbin_rules(db, crs)
        print(f"✅ 创建了 {len(crs)} 条权限规则")
        
        # ==================== 6. 创建默认用户 ====================
        print("📝 创建默认用户...")
        
        # 创建系统管理员用户
        admin_exp = await db.execute(select(User).where(User.username == 'admin'))
        admin_user = admin_exp.scalars().first()
        
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                hashed_password=get_password_hash('admin123'),
                full_name='系统管理员',
                is_admin=True,
                is_active=True,
                is_verified=True
            )
            db.add(admin_user)
            await db.commit()
            await db.refresh(admin_user)
            print("  ✅ 创建管理员用户: admin / admin123")
        
        # 创建任务管理员用户
        manager_exp = await db.execute(select(User).where(User.username == 'task_manager'))
        manager_user = manager_exp.scalars().first()
        
        if not manager_user:
            manager_user = User(
                username='task_manager',
                email='manager@example.com',
                hashed_password=get_password_hash('manager123'),
                full_name='任务管理员',
                is_admin=False,
                is_active=True,
                is_verified=True
            )
            db.add(manager_user)
            await db.commit()
            await db.refresh(manager_user)
            print("  ✅ 创建任务管理员: task_manager / manager123")
        
        # 创建普通用户
        user_exp = await db.execute(select(User).where(User.username == 'user01'))
        normal_user = user_exp.scalars().first()
        
        if not normal_user:
            normal_user = User(
                username='user01',
                email='user01@example.com',
                hashed_password=get_password_hash('user123'),
                full_name='普通用户01',
                is_admin=False,
                is_active=True,
                is_verified=True
            )
            db.add(normal_user)
            await db.commit()
            await db.refresh(normal_user)
            print("  ✅ 创建普通用户: user01 / user123")
        
        # ==================== 7. 分配用户角色 ====================
        print("📝 分配用户角色...")
        
        # 为管理员分配系统管理员角色
        admin_roles = await get_roles_by_uid(db, admin_user.id)
        if len(admin_roles) == 0:
            admin_role = await get_role_by_role_key(db, 'role_sysadmin')
            if admin_role:
                await bind_user_role(db, admin_user.id, admin_role.id)
                print("  ✅ admin 绑定 role_sysadmin")
        
        # 为任务管理员分配角色
        manager_roles = await get_roles_by_uid(db, manager_user.id)
        if len(manager_roles) == 0:
            manager_role = await get_role_by_role_key(db, 'role_task_manager')
            if manager_role:
                await bind_user_role(db, manager_user.id, manager_role.id)
                print("  ✅ task_manager 绑定 role_task_manager")
        
        # 为普通用户分配角色
        user_roles = await get_roles_by_uid(db, normal_user.id)
        if len(user_roles) == 0:
            user_role = await get_role_by_role_key(db, 'role_user')
            if user_role:
                await bind_user_role(db, normal_user.id, user_role.id)
                print("  ✅ user01 绑定 role_user")
        
        print("\n🎉 数据初始化完成！")
        print("\n📋 默认账号信息：")
        print("=" * 60)
        print(f"  系统管理员: admin / admin123")
        print(f"  任务管理员: task_manager / manager123")
        print(f"  普通用户: user01 / user123")
        print("=" * 60)
        print("\n📊 角色权限说明：")
        print("  - role_sysadmin: 拥有所有系统权限")
        print("  - role_task_manager: 可以管理任务、调度、监控")
        print("  - role_user: 可以查看任务列表和执行任务")
        print()


if __name__ == "__main__":
    # 运行方式: python -m src.db_util.init_data
    asyncio.run(create_data())
