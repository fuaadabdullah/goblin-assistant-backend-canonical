"""
Silliconflow provider adapter for health checks and model discovery.
Silliconflow is OpenAI-compatible API.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class SilliconflowAdapter:
    """Adapter for Silliconflow API provider operations."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize Silliconflow adapter.

        Args:
            api_key: Silliconflow API key
            base_url: Optional custom base URL
        """
        self.api_key = api_key
        # Try .com endpoint as alternative to .cn
        self.base_url = base_url or "https://api.siliconflow.com/v1"
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Silliconflow API.

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
            logger.error(f"Silliconflow health check failed: {e}")

            return {
                "healthy": False,
                "response_time_ms": round(response_time, 2),
                "error_rate": 1.0,
                "error": str(e),
                "timestamp": time.time(),
            }

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Silliconflow models.

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
            logger.error(f"Failed to list Silliconflow models: {e}")
            # Fallback to known models if API fails
            return self._get_fallback_models()

    def _get_fallback_models(self) -> List[Dict[str, Any]]:
        """Get fallback list of known Silliconflow models.

        Returns:
            List of known model specifications
        """
        return [
            {
                "id": "Qwen/Qwen2.5-7B-Instruct",
                "name": "Qwen 2.5 7B Instruct",
                "capabilities": ["chat"],
                "context_window": 32768,
                "pricing": {"input": 0.00035, "output": 0.00035},  # per 1K tokens
            },
            {
                "id": "Qwen/Qwen2.5-72B-Instruct",
                "name": "Qwen 2.5 72B Instruct",
                "capabilities": ["chat"],
                "context_window": 32768,
                "pricing": {"input": 0.00056, "output": 0.00056},
            },
            {
                "id": "deepseek-ai/DeepSeek-V3",
                "name": "DeepSeek V3",
                "capabilities": ["chat", "code"],
                "context_window": 64000,
                "pricing": {"input": 0.00027, "output": 0.00110},
            },
            {
                "id": "meta-llama/Llama-3.1-8B-Instruct",
                "name": "Llama 3.1 8B Instruct",
                "capabilities": ["chat"],
                "context_window": 128000,
                "pricing": {"input": 0.00035, "output": 0.00035},
            },
            {
                "id": "meta-llama/Llama-3.1-70B-Instruct",
                "name": "Llama 3.1 70B Instruct",
                "capabilities": ["chat"],
                "context_window": 128000,
                "pricing": {"input": 0.00056, "output": 0.00056},
            },
            {
                "id": "THUDM/glm-4-9b-chat",
                "name": "GLM-4 9B Chat",
                "capabilities": ["chat"],
                "context_window": 8192,
                "pricing": {"input": 0.00035, "output": 0.00035},
            },
        ]

    def _infer_capabilities(self, model_id: str) -> List[str]:
        """Infer capabilities based on model ID.

        Args:
            model_id: Silliconflow model identifier

        Returns:
            List of capability strings
        """
        capabilities = ["chat"]  # All models support chat

        # Code-specific models
        if "deepseek" in model_id.lower() or "coder" in model_id.lower():
            capabilities.append("code")

        # Vision models
        if "vision" in model_id.lower() or "vl" in model_id.lower():
            capabilities.append("vision")

        return capabilities

    def _get_context_window(self, model_id: str) -> int:
        """Get context window size for model.

        Args:
            model_id: Silliconflow model identifier

        Returns:
            Context window size in tokens
        """
        # Known context windows
        if "Qwen2.5" in model_id:
            return 32768
        elif "DeepSeek-V3" in model_id:
            return 64000
        elif "Llama-3.1" in model_id:
            return 128000
        elif "glm-4" in model_id:
            return 8192

        # Default
        return 32768

    def _get_pricing(self, model_id: str) -> Dict[str, float]:
        """Get pricing information for model.

        Args:
            model_id: Silliconflow model identifier

        Returns:
            Dict with pricing per 1K tokens
        """
        # Silliconflow pricing (very competitive rates)
        if "7B" in model_id or "8B" in model_id or "9B" in model_id:
            return {"input": 0.00035, "output": 0.00035}
        elif "70B" in model_id or "72B" in model_id:
            return {"input": 0.00056, "output": 0.00056}
        elif "DeepSeek-V3" in model_id:
            return {"input": 0.00027, "output": 0.00110}

        # Default pricing
        return {"input": 0.0004, "output": 0.0004}

    async def test_completion(
        self, model: str = "Qwen/Qwen2.5-7B-Instruct", max_tokens: int = 10
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
            logger.error(f"Silliconflow completion test failed: {e}")

            return {
                "success": False,
                "response_time_ms": round(response_time, 2),
                "error": str(e),
                "model": model,
            }
