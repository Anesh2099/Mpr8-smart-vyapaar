import os
import redis.asyncio as redis
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    _instance: Optional[redis.Redis] = None

    @classmethod
    def get_instance(cls) -> redis.Redis:
        if cls._instance is None:
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            # decode_responses=True returns strings instead of bytes
            cls._instance = redis.from_url(redis_url, decode_responses=True)
        return cls._instance

    @classmethod
    async def get(cls, key: str) -> Optional[str]:
        if cls._instance is None:
            return None
        try:
            return await cls._instance.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    @classmethod
    async def set(cls, key: str, value: str, ex: Optional[int] = None) -> None:
        if cls._instance is None:
            return
        try:
            await cls._instance.set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    @classmethod
    async def delete(cls, key: str) -> None:
        if cls._instance is None:
            return
        try:
            await cls._instance.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")

    @classmethod
    async def close(cls) -> None:
        if cls._instance is not None:
            try:
                await cls._instance.close()
            except Exception as e:
                logger.error(f"Redis close error: {e}")
            finally:
                cls._instance = None
