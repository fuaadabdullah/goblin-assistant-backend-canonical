"""Prometheus metrics for monitoring and alerting.

Metrics tracked:
- HTTP request count by endpoint, method, status
- Request duration histograms
- Active requests gauge
- Error rate counters
- Custom business metrics (chat completions, token usage, etc.)
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST


# HTTP Metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests in progress",
    ["method", "endpoint"],
)

http_errors_total = Counter(
    "http_errors_total",
    "Total HTTP errors",
    ["method", "endpoint", "error_type"],
)

# Business Metrics
chat_completions_total = Counter(
    "chat_completions_total",
    "Total chat completions requested",
    ["provider", "model"],
)

chat_completion_tokens_total = Counter(
    "chat_completion_tokens_total",
    "Total tokens used in chat completions",
    ["provider", "model", "token_type"],  # token_type: prompt, completion
)

chat_completion_errors_total = Counter(
    "chat_completion_errors_total",
    "Total chat completion errors",
    ["provider", "error_type"],
)

provider_latency_seconds = Histogram(
    "provider_latency_seconds",
    "Provider API call latency in seconds",
    ["provider", "operation"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

# Health Check Metrics
service_health_status = Gauge(
    "service_health_status",
    "Service health status (1=healthy, 0=unhealthy)",
    ["service_name"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics for all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics collection for metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = request.url.path

        # Track in-progress requests
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        start_time = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Record metrics
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=response.status_code,
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            return response

        except Exception as e:
            duration = time.time() - start_time

            # Record error metrics
            http_errors_total.labels(
                method=method,
                endpoint=endpoint,
                error_type=type(e).__name__,
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            raise

        finally:
            # Decrement in-progress counter
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()
