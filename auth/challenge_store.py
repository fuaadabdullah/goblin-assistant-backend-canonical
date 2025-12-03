"""
Challenge Store Service for WebAuthn Passkey Authentication

Provides an abstraction layer for challenge storage with support for:
- In-memory storage (development)
- Redis storage (production)
- Automatic TTL/expiration
- Thread-safe operations
"""

from typing import Optional, Dict
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import os


class ChallengeStore(ABC):
    """Abstract base class for challenge storage"""

    @abstractmethod
    async def set_challenge(
        self, email: str, challenge: str, ttl_minutes: int = 5
    ) -> None:
        """
        Store a challenge for a user with expiration.

        Args:
            email: User's email address (key)
            challenge: Base64url-encoded challenge string
            ttl_minutes: Time-to-live in minutes
        """
        pass

    @abstractmethod
    async def get_challenge(self, email: str) -> Optional[str]:
        """
        Retrieve a challenge for a user.

        Args:
            email: User's email address

        Returns:
            Challenge string if exists and not expired, None otherwise
        """
        pass

    @abstractmethod
    async def delete_challenge(self, email: str) -> bool:
        """
        Delete a challenge (for one-time use).

        Args:
            email: User's email address

        Returns:
            True if challenge existed and was deleted, False otherwise
        """
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """
        Remove expired challenges (for storage backends without auto-expiration).

        Returns:
            Number of expired challenges removed
        """
        pass


class InMemoryChallengeStore(ChallengeStore):
    """
    In-memory challenge storage for development.

    WARNING: Not suitable for production use:
    - Data lost on server restart
    - Not thread-safe without locks
    - Not scalable across multiple server instances
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, any]] = {}

    async def set_challenge(
        self, email: str, challenge: str, ttl_minutes: int = 5
    ) -> None:
        expires = datetime.utcnow() + timedelta(minutes=ttl_minutes)
        self._store[email] = {"challenge": challenge, "expires": expires}

    async def get_challenge(self, email: str) -> Optional[str]:
        if email not in self._store:
            return None

        data = self._store[email]
        if datetime.utcnow() > data["expires"]:
            # Expired, remove it
            del self._store[email]
            return None

        return data["challenge"]

    async def delete_challenge(self, email: str) -> bool:
        if email in self._store:
            del self._store[email]
            return True
        return False

    async def cleanup_expired(self) -> int:
        """Remove expired challenges"""
        now = datetime.utcnow()
        expired_keys = [
            email for email, data in self._store.items() if now > data["expires"]
        ]
        for email in expired_keys:
            del self._store[email]
        return len(expired_keys)


class RedisChallengeStore(ChallengeStore):
    """
    Redis-based challenge storage for production.

    Benefits:
    - Automatic TTL expiration
    - Thread-safe operations
    - Scalable across multiple server instances
    - Persistent across server restarts
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ssl: bool = False,
        key_prefix: str = "passkey:challenge:",
    ):
        """
        Initialize Redis connection.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (if required)
            ssl: Use SSL connection
            key_prefix: Prefix for Redis keys
        """
        import redis

        self.key_prefix = key_prefix
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password if password else None,
            ssl=ssl,
            decode_responses=True,  # Decode bytes to strings
        )

        # Test connection
        try:
            self.redis.ping()
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")

    def _make_key(self, email: str) -> str:
        """Generate Redis key for email"""
        return f"{self.key_prefix}{email}"

    async def set_challenge(
        self, email: str, challenge: str, ttl_minutes: int = 5
    ) -> None:
        key = self._make_key(email)
        # Store challenge with automatic expiration
        self.redis.setex(key, timedelta(minutes=ttl_minutes), challenge)

    async def get_challenge(self, email: str) -> Optional[str]:
        key = self._make_key(email)
        challenge = self.redis.get(key)
        return challenge if challenge else None

    async def delete_challenge(self, email: str) -> bool:
        key = self._make_key(email)
        result = self.redis.delete(key)
        return result > 0

    async def cleanup_expired(self) -> int:
        """
        Redis automatically removes expired keys, so this is a no-op.

        Returns:
            0 (Redis handles expiration automatically)
        """
        return 0


def get_challenge_store() -> ChallengeStore:
    """
    Factory function to get the appropriate challenge store based on environment.

    Returns:
        ChallengeStore instance (InMemory for dev, Redis for production)
    """
    use_redis = os.getenv("USE_REDIS_CHALLENGES", "false").lower() == "true"

    if use_redis:
        # Production: Use Redis
        return RedisChallengeStore(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD", None),
            ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
        )
    else:
        # Development: Use in-memory
        return InMemoryChallengeStore()


# Singleton instance
_challenge_store: Optional[ChallengeStore] = None


def get_challenge_store_instance() -> ChallengeStore:
    """
    Get singleton challenge store instance.

    Returns:
        Shared ChallengeStore instance
    """
    global _challenge_store
    if _challenge_store is None:
        _challenge_store = get_challenge_store()
    return _challenge_store
