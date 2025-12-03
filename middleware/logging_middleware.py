"""Structured JSON logging middleware for production observability.

Features:
- JSON formatted logs for easy parsing
- Request/response logging with timing
- Error tracking with stack traces
- Correlation IDs for request tracing
"""

import time
import logging
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from pythonjsonlogger import jsonlogger


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests/responses with structured JSON format."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate correlation ID for request tracing
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        # Start timer
        start_time = time.time()

        # Extract request details
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                request_body = await request.body()
                # Store for route handlers to access
                request.state.body = request_body
            except Exception:
                pass

        # Log incoming request
        logger.info(
            "incoming_request",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )

        # Process request
        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log successful response
            logger.info(
                "request_completed",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id

            return response

        except Exception as e:
            duration = time.time() - start_time

            # Log error
            logger.error(
                "request_failed",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )

            raise


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure structured JSON logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("goblin_assistant")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create JSON formatter
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
        },
    )

    # Console handler with JSON format
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optionally add file handler for persistent logs
    # file_handler = logging.FileHandler('logs/app.log')
    # file_handler.setFormatter(formatter)
    # logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = setup_logging()
