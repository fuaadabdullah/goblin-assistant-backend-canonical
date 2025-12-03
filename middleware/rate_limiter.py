"""Simple in-memory rate limiting middleware (no external dependencies).

Provides tiered rate limits:
- Auth endpoints: 10/minute (prevent brute force)
- Chat endpoints: 30/minute (LLM calls are expensive)
- Health endpoints: 60/minute (allow monitoring)
- General API: 100/minute (standard rate)

For production with multiple servers, consider using Redis-backed rate limiting.
"""

import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter:
    """Simple in-memory rate limiter using sliding window."""

    def __init__(self):
        # Store: {client_ip: {endpoint: [(timestamp, count)]}}
        self.requests: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))

    def is_allowed(self, client_ip: str, endpoint: str, limit: int, window: int = 60) -> Tuple[bool, int]:
        """Check if request is allowed under rate limit.

        Args:
            client_ip: Client IP address
            endpoint: API endpoint pattern
            limit: Maximum requests allowed
            window: Time window in seconds (default: 60)

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = time.time()
        window_start = now - window

        # Clean old requests
        self.requests[client_ip][endpoint] = [
            ts for ts in self.requests[client_ip][endpoint] if ts > window_start
        ]

        current_count = len(self.requests[client_ip][endpoint])

        if current_count >= limit:
            # Calculate retry_after based on oldest request
            if self.requests[client_ip][endpoint]:
                oldest = self.requests[client_ip][endpoint][0]
                retry_after = int(window - (now - oldest)) + 1
                return False, retry_after
            return False, window

        # Allow request
        self.requests[client_ip][endpoint].append(now)
        return True, 0

    def cleanup_old_entries(self, max_age: int = 300):
        """Cleanup entries older than max_age seconds to prevent memory bloat."""
        now = time.time()
        for client_ip in list(self.requests.keys()):
            for endpoint in list(self.requests[client_ip].keys()):
                self.requests[client_ip][endpoint] = [
                    ts for ts in self.requests[client_ip][endpoint] if now - ts < max_age
                ]
                if not self.requests[client_ip][endpoint]:
                    del self.requests[client_ip][endpoint]
            if not self.requests[client_ip]:
                del self.requests[client_ip]


# Global rate limiter instance
limiter = RateLimiter()


# Endpoint pattern to limit mapping
RATE_LIMITS = {
    "/auth": 10,  # 10 requests per minute
    "/chat": 30,  # 30 requests per minute
    "/health": 60,  # 60 requests per minute
}

DEFAULT_LIMIT = 100  # Default: 100 requests per minute


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits on API endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for metrics endpoint
        if request.url.path == "/metrics":
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Determine rate limit for this endpoint
        limit = DEFAULT_LIMIT
        endpoint_pattern = "default"

        for pattern, pattern_limit in RATE_LIMITS.items():
            if request.url.path.startswith(pattern):
                limit = pattern_limit
                endpoint_pattern = pattern
                break

        # Check rate limit
        allowed, retry_after = limiter.is_allowed(client_ip, endpoint_pattern, limit)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded: {limit} per minute",
                    "retry_after": retry_after,
                },
            )

        # Process request
        response = await call_next(request)
        return response


def rate_limit_exceeded_handler(request: Request, exc: HTTPException):
    """Handler for rate limit exceptions (not needed with middleware approach)."""
    pass
