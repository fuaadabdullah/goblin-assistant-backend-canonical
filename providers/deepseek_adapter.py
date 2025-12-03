"""
DeepSeek provider adapter for health checks and model discovery.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class DeepSeekAdapter:
    """Adapter for DeepSeek API provider operations."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize DeepSeek adapter.

        Args:
            api_key: DeepSeek API key
            base_url: Optional custom base URL
        """
        self.api_key = api_key
        self.base_url = base_url or "https://api.deepseek.com/v1"
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on DeepSeek API.

        Returns:
            Dict containing health status and metrics
        """
        start_time = time.time()
        try:
            # Test with models endpoint
            models_response = await asyncio.get_event_loop().run_in_executor(
                None, self.client.models.list
            )

            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            return {
                "healthy": True,
                "response_time_ms": round(response_time, 2),
                "error_rate": 0.0,
                "available_models": len(models_response.data)
                if hasattr(models_response, "data")
                else 0,
                "timestamp": time.time(),
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"DeepSeek health check failed: {e}")

            return {
                "healthy": False,
                "response_time_ms": round(response_time, 2),
                "error_rate": 1.0,
                "error": str(e),
                "timestamp": time.time(),
            }

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available DeepSeek models.

        Returns:
            List of model information dictionaries
        """
        try:
            models_response = await asyncio.get_event_loop().run_in_executor(
                None, self.client.models.list
            )

            models = []
            for model in models_response.data:
                models.append(
                    {
                        "id": model.id,
                        "name": model.id,
                        "capabilities": self._infer_capabilities(model.id),
                        "context_window": self._get_context_window(model.id),
                        "pricing": self._get_pricing(model.id),
                    }
                )

            return models

        except Exception as e:
            logger.error(f"Failed to list DeepSeek models: {e}")
            # Fallback to known models if API fails
            return self._get_fallback_models()

    def _get_fallback_models(self) -> List[Dict[str, Any]]:
        """Get fallback list of known DeepSeek models.

        Returns:
            List of known model specifications
        """
        return [
            {
                "id": "deepseek-chat",
                "name": "DeepSeek Chat",
                "capabilities": ["chat"],
                "context_window": 32768,
                "pricing": {"input": 0.00014, "output": 0.00028},  # per 1K tokens
            },
            {
                "id": "deepseek-coder",
                "name": "DeepSeek Coder",
                "capabilities": ["chat", "code"],
                "context_window": 32768,
                "pricing": {"input": 0.00014, "output": 0.00028},
            },
            {
                "id": "deepseek-chat-67b",
                "name": "DeepSeek Chat 67B",
                "capabilities": ["chat"],
                "context_window": 4096,
                "pricing": {"input": 0.00014, "output": 0.00028},
            },
            {
                "id": "deepseek-coder-33b",
                "name": "DeepSeek Coder 33B",
                "capabilities": ["chat", "code"],
                "context_window": 16384,
                "pricing": {"input": 0.00014, "output": 0.00028},
            },
        ]

    def _infer_capabilities(self, model_id: str) -> List[str]:
        """Infer capabilities based on model ID.

        Args:
            model_id: DeepSeek model identifier

        Returns:
            List of capability strings
        """
        capabilities = ["chat"]  # All DeepSeek models support chat

        # Code models
        if "coder" in model_id.lower():
            capabilities.append("code")

        return capabilities

    def _get_context_window(self, model_id: str) -> int:
        """Get context window size for model.

        Args:
            model_id: DeepSeek model identifier

        Returns:
            Context window size in tokens
        """
        context_windows = {
            "deepseek-chat": 32768,
            "deepseek-coder": 32768,
            "deepseek-chat-67b": 4096,
            "deepseek-coder-33b": 16384,
        }

        return context_windows.get(model_id, 32768)

    def _get_pricing(self, model_id: str) -> Dict[str, float]:
        """Get pricing information for model.

        Args:
            model_id: DeepSeek model identifier

        Returns:
            Dict with pricing per 1K tokens
        """
        # DeepSeek pricing (subject to change)
        pricing = {
            "deepseek-chat": {"input": 0.00014, "output": 0.00028},
            "deepseek-coder": {"input": 0.00014, "output": 0.00028},
            "deepseek-chat-67b": {"input": 0.00014, "output": 0.00028},
            "deepseek-coder-33b": {"input": 0.00014, "output": 0.00028},
        }

        return pricing.get(model_id, {"input": 0.00014, "output": 0.00028})

    async def test_completion(
        self, model: str = "deepseek-chat", max_tokens: int = 10
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
                lambda: self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hello, test message"}],
                    max_tokens=max_tokens,
                ),
            )

            response_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "response_time_ms": round(response_time, 2),
                "tokens_used": response.usage.total_tokens
                if hasattr(response, "usage")
                else None,
                "model": model,
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"DeepSeek completion test failed: {e}")

            return {
                "success": False,
                "response_time_ms": round(response_time, 2),
                "error": str(e),
                "model": model,
            }
