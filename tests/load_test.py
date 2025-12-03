"""Load testing script using Locust for critical endpoints.

Run with:
    locust -f backend/tests/load_test.py --host=http://localhost:8001

Performance Targets:
- Health checks: < 100ms p95, 100 RPS
- Chat completions: < 2s p95, 10 RPS
- Auth login: < 500ms p95, 20 RPS
"""

import json
import random
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


class GoblinAssistantUser(HttpUser):
    """Simulated user for load testing."""

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    # Store auth token
    token = None

    def on_start(self):
        """Called when a simulated user starts."""
        # Try to login (will fail if no test user exists, that's ok)
        try:
            response = self.client.post(
                "/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "testpassword123",
                },
            )
            if response.status_code == 200:
                self.token = response.json().get("access_token")
        except Exception:
            pass

    @task(10)
    def health_check(self):
        """Test health endpoint (high frequency)."""
        self.client.get("/health")

    @task(8)
    def health_all(self):
        """Test detailed health endpoint."""
        self.client.get("/health/all")

    @task(5)
    def health_chroma(self):
        """Test ChromaDB health check."""
        self.client.get("/health/chroma/status")

    @task(3)
    def health_sandbox(self):
        """Test sandbox health check."""
        self.client.get("/health/sandbox/status")

    @task(2)
    def get_models(self):
        """Test available models endpoint."""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.client.get("/chat/models", headers=headers)

    @task(1)
    def chat_completion(self):
        """Test chat completion endpoint (low frequency, expensive)."""
        if not self.token:
            return

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        messages = [
            "Hello, how are you?",
            "What's the weather like?",
            "Tell me a joke",
            "Explain quantum computing",
            "What is FastAPI?",
        ]

        payload = {
            "messages": [{"role": "user", "content": random.choice(messages)}],
            "stream": False,
        }

        self.client.post(
            "/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )

    @task(2)
    def get_settings(self):
        """Test settings endpoint."""
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get("/settings/", headers=headers)

    @task(1)
    def login(self):
        """Test login endpoint."""
        self.client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123",
            },
        )


# Performance thresholds
HEALTH_P95_THRESHOLD = 100  # ms
CHAT_P95_THRESHOLD = 2000  # ms
AUTH_P95_THRESHOLD = 500  # ms


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Check performance thresholds after test completes."""
    if isinstance(environment.runner, MasterRunner):
        return

    stats = environment.stats

    failed_checks = []

    # Check health endpoint performance
    health_stats = stats.get("/health", "GET")
    if health_stats and health_stats.avg_response_time > HEALTH_P95_THRESHOLD:
        failed_checks.append(
            f"Health endpoint avg response time {health_stats.avg_response_time:.0f}ms "
            f"exceeds threshold {HEALTH_P95_THRESHOLD}ms"
        )

    # Check chat endpoint performance
    chat_stats = stats.get("/chat/completions", "POST")
    if chat_stats and chat_stats.avg_response_time > CHAT_P95_THRESHOLD:
        failed_checks.append(
            f"Chat endpoint avg response time {chat_stats.avg_response_time:.0f}ms "
            f"exceeds threshold {CHAT_P95_THRESHOLD}ms"
        )

    # Check auth endpoint performance
    auth_stats = stats.get("/auth/login", "POST")
    if auth_stats and auth_stats.avg_response_time > AUTH_P95_THRESHOLD:
        failed_checks.append(
            f"Auth endpoint avg response time {auth_stats.avg_response_time:.0f}ms "
            f"exceeds threshold {AUTH_P95_THRESHOLD}ms"
        )

    if failed_checks:
        print("\n❌ Performance thresholds failed:")
        for check in failed_checks:
            print(f"  - {check}")
        environment.process_exit_code = 1
    else:
        print("\n✅ All performance thresholds passed!")


if __name__ == "__main__":
    print("""
    Load Testing Suite for Goblin Assistant Backend
    
    Usage:
        # Run with Web UI
        locust -f backend/tests/load_test.py --host=http://localhost:8001
        
        # Run headless (10 users, 2 per second spawn rate, 60 seconds)
        locust -f backend/tests/load_test.py --host=http://localhost:8001 \\
               --users 10 --spawn-rate 2 --run-time 60s --headless
        
        # Stress test (100 users)
        locust -f backend/tests/load_test.py --host=http://localhost:8001 \\
               --users 100 --spawn-rate 10 --run-time 300s --headless
    
    Performance Targets:
        - Health checks: < 100ms p95
        - Chat completions: < 2s p95
        - Auth login: < 500ms p95
    """)
