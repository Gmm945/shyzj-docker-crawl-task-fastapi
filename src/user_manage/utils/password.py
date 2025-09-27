"""密码工具模块"""
import os
import warnings
from passlib.context import CryptContext

# 设置环境变量来抑制bcrypt警告
os.environ.setdefault("PASSLIB_SUPPRESS_WARNINGS", "1")

# 忽略bcrypt版本警告
warnings.filterwarnings("ignore", message=".*bcrypt version.*")
warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)
