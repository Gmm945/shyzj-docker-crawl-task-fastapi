"""用户管理模块工具函数"""
import random
import string
from ..db_util.db import get_casbin_e


async def batch_verify_enforces(enforces):
    """
    批量验证 Casbin 规则
    
    Args:
        enforces: 规则列表，每个元素是一个元组 (subject, object, action)
    
    Returns:
        list: 每个规则的验证结果 (True/False)
    
    Example:
        >>> enforces = [
        ...     ("role_admin", "task", "create"),
        ...     ("role_admin", "task", "read"),
        ...     ("role_admin", "user", "delete")
        ... ]
        >>> results = await batch_verify_enforces(enforces)
        >>> # 返回: [True, True, False]
    """
    e = await get_casbin_e()
    return e.batch_enforce(enforces)  # batch_enforce 返回 list，不是 awaitable


async def generate_password(length: int = 12) -> str:
    """
    生成随机密码
    
    Args:
        length: 密码长度，默认 12
    
    Returns:
        str: 随机生成的密码
    """
    characters = string.ascii_letters + string.digits
    # 使用随机选择生成密码
    password = ''.join(random.choice(characters) for _ in range(length))
    return password
