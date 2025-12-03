"""
Anthropic provider adapter for health checks and model discovery.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
import anthropic
import logging

logger = logging.getLogger(__name__)


class AnthropicAdapter:
    """Adapter for Anthropic API provider operations."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize Anthropic adapter.

        Args:
            api_key: Anthropic API key
            base_url: Optional custom base URL
        """
        self.api_key = api_key
        self.base_url = base_url
        # Only pass base_url if explicitly provided (None is valid for Anthropic default)
        if base_url:
            self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=api_key)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Anthropic API.

        Returns:
            Dict containing health status and metrics
        """
        start_time = time.time()
        try:
            # Test with a simple message to check API availability
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hello"}],
                ),
            )

            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            return {
                "healthy": True,
                "response_time_ms": round(response_time, 2),
                "error_rate": 0.0,
                "available_models": len(self._get_available_models()),
                "timestamp": time.time(),
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Anthropic health check failed: {e}")

            return {
                "healthy": False,
                "response_time_ms": round(response_time, 2),
                "error_rate": 1.0,
                "error": str(e),
                "timestamp": time.time(),
            }

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Anthropic models.

        Returns:
            List of model information dictionaries
        """
        try:
            # Anthropic doesn't have a models list endpoint, so we return known models
            models = self._get_available_models()

            result = []
            for model_info in models:
                result.append(
                    {
                        "id": model_info["id"],
                        "name": model_info["name"],
                        "capabilities": model_info["capabilities"],
                        "context_window": model_info["context_window"],
                        "pricing": model_info["pricing"],
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Failed to list Anthropic models: {e}")
            return []

    def _get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Anthropic models with their specifications.

        Returns:
            List of model specifications
        """
        return [
            {
                "id": "claude-3-opus-20240229",
                "name": "Claude 3 Opus",
                "capabilities": ["chat", "vision"],
                "context_window": 200000,
                "pricing": {"input": 0.015, "output": 0.075},  # per 1K tokens
            },
            {
                "id": "claude-3-sonnet-20240229",
                "name": "Claude 3 Sonnet",
                "capabilities": ["chat", "vision"],
                "context_window": 200000,
                "pricing": {"input": 0.003, "output": 0.015},
            },
            {
                "id": "claude-3-haiku-20240307",
                "name": "Claude 3 Haiku",
                "capabilities": ["chat", "vision"],
                "context_window": 200000,
                "pricing": {"input": 0.00025, "output": 0.00125},
            },
            {
                "id": "claude-3-5-sonnet-20240620",
                "name": "Claude 3.5 Sonnet",
                "capabilities": ["chat", "vision"],
                "context_window": 200000,
                "pricing": {"input": 0.003, "output": 0.015},
            },
            {
                "id": "claude-2.1",
                "name": "Claude 2.1",
                "capabilities": ["chat"],
                "context_window": 200000,
                "pricing": {"input": 0.008, "output": 0.024},
            },
            {
                "id": "claude-2.0",
                "name": "Claude 2.0",
                "capabilities": ["chat"],
                "context_window": 100000,
                "pricing": {"input": 0.008, "output": 0.024},
            },
            {
                "id": "claude-instant-1.2",
                "name": "Claude Instant 1.2",
                "capabilities": ["chat"],
                "context_window": 100000,
                "pricing": {"input": 0.0008, "output": 0.0024},
            },
        ]

    async def test_completion(
        self, model: str = "claude-3-haiku-20240307", max_tokens: int = 10
    ) -> Dict[str, Any]:
        """Test completion capability.

        Args:
            model: Model to test
            max_tokens: Maximum tokens for response

        Returns:
            Dict with test results
        """
        start_time = time.time()
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": "Hello, test message"}],
                ),
            )

            response_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "response_time_ms": round(response_time, 2),
                "tokens_used": response.usage.input_tokens
                + response.usage.output_tokens
                if hasattr(response, "usage")
                else None,
                "model": model,
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Anthropic completion test failed: {e}")

            return {
                "success": False,
                "response_time_ms": round(response_time, 2),
                "error": str(e),
                "model": model,
            }
