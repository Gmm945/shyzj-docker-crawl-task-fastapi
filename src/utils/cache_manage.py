import hashlib
import json
from typing import Any, Optional
from loguru import logger
import redis.asyncio as redis
import redis as redis_sync
from ..config.auth_config import settings

class AsyncCacheManager:
    def __init__(self, redis_db: int = None, default_ttl: int = 7200):
        """
        初始化异步缓存管理器
        :param redis_db: Redis 数据库编号，如果为None则从settings获取
        :param default_ttl: 默认缓存过期时间，默认为 7200 秒（2 小时）
        """
        self.redis_host = settings.REDIS_HOST
        self.redis_port = settings.REDIS_PORT
        self.redis_db = redis_db if redis_db is not None else settings.REDIS_DB
        self.redis_password = settings.REDIS_PASSWORD
        self.default_ttl = default_ttl
        self.redis_client = None
        self._sync_pool: Optional[redis_sync.ConnectionPool] = None
        self._redis_client_sync: Optional[redis_sync.Redis] = None

    async def connect_redis(self):
        try:
            redis_kwargs = {
                "host": self.redis_host,
                "port": self.redis_port,
                "db": self.redis_db,
                "decode_responses": True
            }
            if self.redis_password:
                redis_kwargs["password"] = self.redis_password
                
            self.redis_client = redis.Redis(**redis_kwargs)
            logger.info("Redis 连接成功")
        except redis.ConnectionError as e:
            logger.error(f"Redis 连接失败: {e}")
            raise
        except redis.TimeoutError as e:
            logger.error(f"Redis 连接超时: {e}")
            raise
        except Exception as e:
            logger.error(f"未知错误: {e}")
            raise

    def _generate_cache_key(self, namespace: str, keys: list[str], use_hash: bool = True) -> str:
        key = f"{namespace}:" + ":".join(keys)
        if use_hash and len(key) > 200:
            key = hashlib.sha256(key.encode()).hexdigest()
        return key

    async def close_redis(self):
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis 连接已关闭")

    async def get_cache(self, namespace: str, keys: list[str]) -> Optional[Any]:
        if not self.redis_client:
            logger.error("Redis 连接未建立，无法获取缓存")
            return None
        key = self._generate_cache_key(namespace, keys)
        try:
            cached_data = await self.redis_client.get(key)
            if cached_data:
                logger.info(f"缓存获取成功: key={key}")
                return json.loads(cached_data)
            logger.info(f"缓存未找到: key={key}")
            return None
        except Exception as e:
            logger.error(f"获取缓存失败: key={key}, error={e}")
            return None

    async def set_cache(self, namespace: str, keys: list[str], data: Any, ttl: Optional[int] = None, forever: Optional[bool] = False) -> bool:
        if not self.redis_client:
            logger.error("Redis 连接未建立，无法设置缓存")
            return False
        try:
            key = self._generate_cache_key(namespace, keys)
            # 如果 ttl 为 None，使用默认的 ttl
            if ttl is None:
                ttl = self.default_ttl
            # 如果 ttl 为 None 且 forever 为 True，缓存永不过期
            if forever:
                await self.redis_client.set(key, json.dumps(data))  # 不传 ttl 参数，缓存永不过期
            else:
                await self.redis_client.set(key, json.dumps(data), ex=ttl)  # 设置过期时间
            logger.info(f"缓存存储成功: key={key}, ttl={ttl if not forever else 'forever'}")
            return True
        except Exception as e:
            logger.error(f"缓存存储失败: key={key}, error={e}")
            return False

    def set_cache_sync(self, namespace: str, keys: list[str], data: Any, ttl: Optional[int] = None, forever: Optional[bool] = False) -> bool:
        """
        同步方式设置缓存，适用于非异步上下文（例如 Celery/后台任务）以避免事件循环问题。
        """
        try:
            # lazy init sync client + pool, reuse across calls
            if self._redis_client_sync is None:
                if self._sync_pool is None:
                    pool_kwargs = {
                        "host": self.redis_host,
                        "port": int(self.redis_port) if isinstance(self.redis_port, str) else self.redis_port,
                        "db": self.redis_db,
                        "decode_responses": True,
                    }
                    if self.redis_password:
                        pool_kwargs["password"] = self.redis_password
                        
                    self._sync_pool = redis_sync.ConnectionPool(**pool_kwargs)
                self._redis_client_sync = redis_sync.Redis(connection_pool=self._sync_pool)
            client = self._redis_client_sync
            key = self._generate_cache_key(namespace, keys)
            if ttl is None:
                ttl = self.default_ttl
            payload = json.dumps(data)
            if forever:
                client.set(key, payload)
            else:
                client.set(key, payload, ex=ttl)
            logger.info(f"缓存存储成功(Sync): key={key}, ttl={ttl if not forever else 'forever'}")
            return True
        except Exception as e:
            logger.error(f"缓存存储失败(Sync): namespace={namespace}, keys={keys}, error={e}")
            return False

    async def delete_cache(self, namespace: str, keys: list[str]) -> bool:
        if not self.redis_client:
            logger.error("Redis 连接未建立，无法删除缓存")
            return False
        try:
            key = self._generate_cache_key(namespace, keys)
            await self.redis_client.delete(key)
            logger.info(f"缓存项 {key} 已被删除")
            return True
        except Exception as e:
            logger.error(f"缓存删除失败: key={key}, error={e}")
            return False

async_cache_manager = AsyncCacheManager()

async def get_cache_manager() -> AsyncCacheManager:
    """获取缓存管理器实例，如果未连接则自动连接"""
    if not async_cache_manager.redis_client:
        await async_cache_manager.connect_redis()
    return async_cache_manager