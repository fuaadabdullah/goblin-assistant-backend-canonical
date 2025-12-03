"""
OpenAI provider adapter for health checks and model discovery.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class OpenAIAdapter:
    """Adapter for OpenAI API provider operations."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key
            base_url: Optional custom base URL
        """
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on OpenAI API.

        Returns:
            Dict containing health status and metrics
        """
        start_time = time.time()
        try:
            # Simple health check using models endpoint
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
            logger.error(f"OpenAI health check failed: {e}")

            return {
                "healthy": False,
                "response_time_ms": round(response_time, 2),
                "error_rate": 1.0,
                "error": str(e),
                "timestamp": time.time(),
            }

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available OpenAI models.

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
            logger.error(f"Failed to list OpenAI models: {e}")
            return []

    def _infer_capabilities(self, model_id: str) -> List[str]:
        """Infer capabilities based on model ID.

        Args:
            model_id: OpenAI model identifier

        Returns:
            List of capability strings
        """
        capabilities = ["chat"]  # All OpenAI models support chat

        # GPT-4 models support vision
        if "gpt-4" in model_id and (
            "vision" in model_id or model_id.startswith("gpt-4")
        ):
            capabilities.append("vision")

        # GPT-3.5 and GPT-4 support embeddings (though dedicated embedding models exist)
        if "gpt" in model_id:
            capabilities.append("embeddings")

        # Add function calling for newer models
        if any(x in model_id for x in ["gpt-4", "gpt-3.5-turbo"]):
            capabilities.append("functions")

        return capabilities

    def _get_context_window(self, model_id: str) -> int:
        """Get context window size for model.

        Args:
            model_id: OpenAI model identifier

        Returns:
            Context window size in tokens
        """
        # Context windows based on OpenAI documentation
        context_windows = {
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-4-1106-preview": 128000,
            "gpt-4-vision-preview": 128000,
            "gpt-4-turbo": 128000,
            "gpt-4-turbo-preview": 128000,
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
            "gpt-3.5-turbo-1106": 16384,
            "text-davinci-003": 4097,
            "text-davinci-002": 4097,
            "text-curie-001": 2049,
            "text-babbage-001": 2049,
            "text-ada-001": 2049,
        }

        # Default to 4096 for unknown models
        return context_windows.get(model_id, 4096)

    def _get_pricing(self, model_id: str) -> Dict[str, float]:
        """Get pricing information for model.

        Args:
            model_id: OpenAI model identifier

        Returns:
            Dict with pricing per 1K tokens
        """
        # Pricing in USD per 1K tokens (approximate, subject to change)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-32k": {"input": 0.06, "output": 0.12},
            "gpt-4-1106-preview": {"input": 0.01, "output": 0.03},
            "gpt-4-vision-preview": {"input": 0.01, "output": 0.03},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
            "gpt-3.5-turbo-1106": {"input": 0.001, "output": 0.002},
        }

        return pricing.get(model_id, {"input": 0.002, "output": 0.002})

    async def test_completion(
        self, model: str = "gpt-3.5-turbo", max_tokens: int = 10
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
            logger.error(f"OpenAI completion test failed: {e}")

            return {
                "success": False,
                "response_time_ms": round(response_time, 2),
                "error": str(e),
                "model": model,
            }
