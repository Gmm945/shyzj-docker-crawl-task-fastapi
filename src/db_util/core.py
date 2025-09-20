from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_async_session
from ..utils.cache_manage import AsyncCacheManager, get_cache_manager


DBSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
CacheManager = Annotated[AsyncCacheManager, Depends(get_cache_manager)]
